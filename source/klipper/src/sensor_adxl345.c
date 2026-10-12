// Support for gathering acceleration data from ADXL345 chip
//
// Copyright (C) 2020  Kevin O'Connor <kevin@koconnor.net>
//
// This file may be distributed under the terms of the GNU GPLv3 license.

#include <string.h> // memcpy
#include "board/irq.h" // irq_disable
#include "board/misc.h" // timer_read_time
#include "basecmd.h" // oid_alloc
#include "command.h" // DECL_COMMAND
#include "sched.h" // DECL_TASK
#include "spicmds.h" // spidev_transfer
#include "trsync.h" // trsync_do_trigger

struct adxl345 {
    struct timer timer, tap_timer;
    uint32_t rest_ticks;
    uint32_t tap_rest_ticks, tap_trigger_clock, tap_query_ticks;
    struct spidev_s *spi;
    struct trsync *tap_ts;
    uint32_t tap_poll_count;
    uint16_t sequence, limit_count;
    uint8_t flags, data_count, tap_flags, tap_source, tap_trigger_reason;
    uint8_t data[50];
};

enum {
    AX_HAVE_START = 1<<0, AX_RUNNING = 1<<1, AX_PENDING = 1<<2,
};

enum {
    AX_TAP_ARM = 1<<0, AX_TAP_RUNNING = 1<<1,
};

static struct task_wake adxl345_wake;

// Event handler that wakes adxl345_task() periodically
static uint_fast8_t
adxl345_event(struct timer *timer)
{
    struct adxl345 *ax = container_of(timer, struct adxl345, timer);
    ax->flags |= AX_PENDING;
    sched_wake_task(&adxl345_wake);
    return SF_DONE;
}

void
command_config_adxl345(uint32_t *args)
{
    struct adxl345 *ax = oid_alloc(args[0], command_config_adxl345
                                   , sizeof(*ax));
    ax->timer.func = adxl345_event;
    ax->spi = spidev_oid_lookup(args[1]);
}
DECL_COMMAND(command_config_adxl345, "config_adxl345 oid=%c spi_oid=%c");

// Report local measurement buffer
static void
adxl_report(struct adxl345 *ax, uint8_t oid)
{
    sendf("adxl345_data oid=%c sequence=%hu data=%*s"
          , oid, ax->sequence, ax->data_count, ax->data);
    ax->data_count = 0;
    ax->sequence++;
}

// Report buffer and fifo status
static void
adxl_status(struct adxl345 *ax, uint_fast8_t oid
            , uint32_t time1, uint32_t time2, uint_fast8_t fifo)
{
    sendf("adxl345_status oid=%c clock=%u query_ticks=%u next_sequence=%hu"
          " buffered=%c fifo=%c limit_count=%hu"
          , oid, time1, time2-time1, ax->sequence
          , ax->data_count, fifo, ax->limit_count);
}

// Helper code to reschedule the adxl345_event() timer
static void
adxl_reschedule_timer(struct adxl345 *ax)
{
    irq_disable();
    ax->timer.waketime = timer_read_time() + ax->rest_ticks;
    sched_add_timer(&ax->timer);
    irq_enable();
}

// Chip registers
#define AR_POWER_CTL   0x2D
#define AR_INT_ENABLE  0x2E
#define AR_INT_SOURCE  0x30
#define AR_DATAX0      0x32
#define AR_FIFO_STATUS 0x39
#define AM_READ  0x80
#define AM_MULTI 0x40

#define SINGLE_TAP 0x40

#define SET_FIFO_CTL 0x90

// Timer callback for ADXL345 Single Tap polling
static uint_fast8_t
adxl345_tap_event(struct timer *timer)
{
    struct adxl345 *ax = container_of(timer, struct adxl345, tap_timer);
    if (ax->tap_flags & AX_TAP_ARM) {
        // Clear stale events and enable only the Single Tap interrupt.
        uint8_t clear_msg[2] = { AR_INT_SOURCE | AM_READ, 0x00 };
        spidev_transfer(ax->spi, 1, sizeof(clear_msg), clear_msg);
        uint8_t enable_msg[2] = { AR_INT_ENABLE, SINGLE_TAP };
        spidev_transfer(ax->spi, 0, sizeof(enable_msg), enable_msg);
        ax->tap_flags = AX_TAP_RUNNING;
        ax->tap_timer.waketime += ax->tap_rest_ticks;
        return SF_RESCHEDULE;
    }

    uint8_t msg[2] = { AR_INT_SOURCE | AM_READ, 0x00 };
    uint32_t time1 = timer_read_time();
    spidev_transfer(ax->spi, 1, sizeof(msg), msg);
    uint32_t time2 = timer_read_time();
    ax->tap_query_ticks = time2 - time1;
    ax->tap_poll_count++;
    if (msg[1] & SINGLE_TAP) {
        ax->tap_source = msg[1];
        ax->tap_trigger_clock = time2;
        ax->tap_flags = 0;
        trsync_do_trigger(ax->tap_ts, ax->tap_trigger_reason);
        return SF_DONE;
    }
    ax->tap_timer.waketime += ax->tap_rest_ticks;
    return SF_RESCHEDULE;
}

// Start or stop scheduled Single Tap polling
void
command_adxl345_tap_home(uint32_t *args)
{
    struct adxl345 *ax = oid_lookup(args[0], command_config_adxl345);
    sched_del_timer(&ax->tap_timer);
    ax->tap_flags = 0;
    ax->tap_ts = NULL;
    if (!args[2])
        return;
    ax->tap_timer.func = adxl345_tap_event;
    ax->tap_timer.waketime = args[1];
    ax->tap_rest_ticks = args[2];
    ax->tap_ts = trsync_oid_lookup(args[3]);
    ax->tap_trigger_reason = args[4];
    ax->tap_trigger_clock = ax->tap_query_ticks = ax->tap_poll_count = 0;
    ax->tap_source = 0;
    ax->tap_flags = AX_TAP_ARM;
    sched_add_timer(&ax->tap_timer);
}
DECL_COMMAND(command_adxl345_tap_home,
             "adxl345_tap_home oid=%c clock=%u rest_ticks=%u"
             " trsync_oid=%c trigger_reason=%c");

// Report the latest Single Tap polling state without clearing chip registers
void
command_adxl345_tap_query_state(uint32_t *args)
{
    uint8_t oid = args[0];
    struct adxl345 *ax = oid_lookup(oid, command_config_adxl345);
    sendf("adxl345_tap_state oid=%c homing=%c trigger_clock=%u"
          " int_source=%c poll_count=%u query_ticks=%u"
          , oid, !!ax->tap_flags, ax->tap_trigger_clock, ax->tap_source
          , ax->tap_poll_count, ax->tap_query_ticks);
}
DECL_COMMAND(command_adxl345_tap_query_state,
             "adxl345_tap_query_state oid=%c");

// Query accelerometer data
static void
adxl_query(struct adxl345 *ax, uint8_t oid)
{
    // Read data
    uint8_t msg[9] = { AR_DATAX0 | AM_READ | AM_MULTI, 0, 0, 0, 0, 0, 0, 0, 0 };
    spidev_transfer(ax->spi, 1, sizeof(msg), msg);
    // Extract x, y, z measurements
    uint_fast8_t fifo_status = msg[8] & ~0x80; // Ignore trigger bit
    uint8_t *d = &ax->data[ax->data_count];
    if (((msg[2] & 0xf0) && (msg[2] & 0xf0) != 0xf0)
        || ((msg[4] & 0xf0) && (msg[4] & 0xf0) != 0xf0)
        || ((msg[6] & 0xf0) && (msg[6] & 0xf0) != 0xf0)
        || (msg[7] != SET_FIFO_CTL) || (fifo_status > 32)) {
        // Data error - may be a CS, MISO, MOSI, or SCLK glitch
        d[0] = d[1] = d[2] = d[3] = d[4] = 0xff;
        fifo_status = 0;
    } else {
        // Copy data
        d[0] = msg[1]; // x low bits
        d[1] = msg[3]; // y low bits
        d[2] = msg[5]; // z low bits
        d[3] = (msg[2] & 0x1f) | (msg[6] << 5); // x high bits and z high bits
        d[4] = (msg[4] & 0x1f) | ((msg[6] << 2) & 0x60); // y high and z high
    }
    ax->data_count += 5;
    if (ax->data_count + 5 > ARRAY_SIZE(ax->data))
        adxl_report(ax, oid);
    // Check fifo status
    if (fifo_status >= 31)
        ax->limit_count++;
    if (fifo_status > 1 && fifo_status <= 32) {
        // More data in fifo - wake this task again
        sched_wake_task(&adxl345_wake);
    } else if (ax->flags & AX_RUNNING) {
        // Sleep until next check time
        sched_del_timer(&ax->timer);
        ax->flags &= ~AX_PENDING;
        adxl_reschedule_timer(ax);
    }
}

// Startup measurements
static void
adxl_start(struct adxl345 *ax, uint8_t oid)
{
    sched_del_timer(&ax->timer);
    ax->flags = AX_RUNNING;
    uint8_t msg[2] = { AR_POWER_CTL, 0x08 };
    spidev_transfer(ax->spi, 0, sizeof(msg), msg);
    adxl_reschedule_timer(ax);
}

// End measurements
static void
adxl_stop(struct adxl345 *ax, uint8_t oid)
{
    // Disable measurements
    sched_del_timer(&ax->timer);
    ax->flags = 0;
    uint8_t msg[2] = { AR_POWER_CTL, 0x00 };
    uint32_t end1_time = timer_read_time();
    spidev_transfer(ax->spi, 0, sizeof(msg), msg);
    uint32_t end2_time = timer_read_time();
    // Drain any measurements still in fifo
    uint_fast8_t i;
    for (i=0; i<33; i++) {
        msg[0] = AR_FIFO_STATUS | AM_READ;
        msg[1] = 0x00;
        spidev_transfer(ax->spi, 1, sizeof(msg), msg);
        uint_fast8_t fifo_status = msg[1] & ~0x80;
        if (!fifo_status)
            break;
        if (fifo_status <= 32)
            adxl_query(ax, oid);
    }
    // Report final data
    if (ax->data_count)
        adxl_report(ax, oid);
    adxl_status(ax, oid, end1_time, end2_time, msg[1]);
}

void
command_query_adxl345(uint32_t *args)
{
    struct adxl345 *ax = oid_lookup(args[0], command_config_adxl345);

    if (!args[2]) {
        // End measurements
        adxl_stop(ax, args[0]);
        return;
    }
    // Start new measurements query
    sched_del_timer(&ax->timer);
    ax->timer.waketime = args[1];
    ax->rest_ticks = args[2];
    ax->flags = AX_HAVE_START;
    ax->sequence = ax->limit_count = 0;
    ax->data_count = 0;
    sched_add_timer(&ax->timer);
}
DECL_COMMAND(command_query_adxl345,
             "query_adxl345 oid=%c clock=%u rest_ticks=%u");

void
command_query_adxl345_status(uint32_t *args)
{
    struct adxl345 *ax = oid_lookup(args[0], command_config_adxl345);
    uint8_t msg[2] = { AR_FIFO_STATUS | AM_READ, 0x00 };
    uint32_t time1 = timer_read_time();
    spidev_transfer(ax->spi, 1, sizeof(msg), msg);
    uint32_t time2 = timer_read_time();
    adxl_status(ax, args[0], time1, time2, msg[1]);
}
DECL_COMMAND(command_query_adxl345_status, "query_adxl345_status oid=%c");

void
adxl345_task(void)
{
    if (!sched_check_wake(&adxl345_wake))
        return;
    uint8_t oid;
    struct adxl345 *ax;
    foreach_oid(oid, ax, command_config_adxl345) {
        uint_fast8_t flags = ax->flags;
        if (!(flags & AX_PENDING))
            continue;
        if (flags & AX_HAVE_START)
            adxl_start(ax, oid);
        else
            adxl_query(ax, oid);
    }
}
DECL_TASK(adxl345_task);

void
adxl345_tap_shutdown(void)
{
    uint8_t oid;
    struct adxl345 *ax;
    foreach_oid(oid, ax, command_config_adxl345) {
        sched_del_timer(&ax->tap_timer);
        ax->tap_flags = 0;
        ax->tap_ts = NULL;
    }
}
DECL_SHUTDOWN(adxl345_tap_shutdown);
