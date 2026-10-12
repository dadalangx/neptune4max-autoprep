"""Cross-Python tests with real vendor bed-mesh finalization and simulated motion."""
import math,os,sys,types,unittest
try:
    import imp
    load_source=imp.load_source
except ImportError:
    import importlib.util
    def load_source(name,path):
        spec=importlib.util.spec_from_file_location(name,path)
        module=importlib.util.module_from_spec(spec);sys.modules[name]=module
        spec.loader.exec_module(module)
        return module
ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
extras=types.ModuleType('_adaptive_mesh_drift_test');extras.__path__=[];sys.modules['_adaptive_mesh_drift_test']=extras
manual=types.ModuleType('_adaptive_mesh_drift_test.manual_probe')
manual.verify_no_manual_probe=lambda printer: None
sys.modules['_adaptive_mesh_drift_test.manual_probe']=manual;extras.manual_probe=manual
probe_module=types.ModuleType('_adaptive_mesh_drift_test.probe')
sys.modules['_adaptive_mesh_drift_test.probe']=probe_module;extras.probe=probe_module
module=load_source('_adaptive_mesh_drift_test.adaptive_mesh_drift',os.path.join(ROOT,'source','klipper','klippy','extras','adaptive_mesh_drift.py'))
native=load_source('_adaptive_mesh_drift_test.native_bed_mesh',os.path.join(ROOT,'tests','fixtures','vendor-bed-mesh-3387a9c2.py'))

class Command:
    error=RuntimeError
    def __init__(self,params=None):self.params=params or {};self.messages=[]
    def get(self,name,default=None):return self.params.get(name,default)
    def get_command_parameters(self):return dict(self.params)
    def get_float(self,name,default=None,**limits):
        value=float(self.params.get(name,default))
        for key,bound in limits.items():
            if (key=='minval' and value<bound) or (key=='maxval' and value>bound) or (key=='above' and value<=bound):raise self.error('limit')
        return value
    def respond_info(self,message):self.messages.append(message)

class GCode:
    error=RuntimeError
    def __init__(self):self.commands={};self.messages=[]
    def register_command(self,name,handler,**kwargs):self.commands[name]=handler
    def create_gcode_command(self,name,line,params):return Command(params)
    def respond_info(self,message):self.messages.append(message)

class Toolhead:
    def __init__(self):self.clock=0.;self.position=[239.25,194.55,10.,0.];self.moves=[];self.homed='xyz'
    def manual_move(self,coord,speed):
        old=self.position[:]
        for i,value in enumerate(coord):
            if value is not None:self.position[i]=value
        self.clock+=math.sqrt(sum((a-b)**2 for a,b in zip(old,self.position)))/speed+.01
        self.moves.append((coord,speed))
    def get_last_move_time(self):return self.clock
    def get_status(self,eventtime):return {'homed_axes':self.homed,'axis_minimum':[-.1,-.1,-5.,0.],'axis_maximum':[430.1,430.1,482.5,0.]}
    def dwell(self,seconds):self.clock+=seconds
    def wait_moves(self):self.clock+=.1

class Probe:
    def __init__(self,toolhead):self.th=toolhead;self.calls=[];self.begins=0;self.ends=0;self.fail_at=None;self.drift_rate=.001
    def get_offsets(self):return (-24.25,20.45,0.)
    def get_lift_speed(self,command):return 8.
    def multi_probe_begin(self):self.begins+=1
    def multi_probe_end(self):self.ends+=1
    @staticmethod
    def shape(x,y):return (x-215.)*.002+(y-215.)*.003
    def run_probe(self,command):
        count=int(command.get('SAMPLES',3));result=command.get('SAMPLES_RESULT','median')
        offsets=self.get_offsets();x=self.th.position[0]+offsets[0];y=self.th.position[1]+offsets[1]
        self.calls.append((x,y,count,result))
        if self.fail_at==len(self.calls):raise RuntimeError('simulated probe failure')
        values=[]
        for unused in range(count):
            self.th.clock+=1.
            values.append(self.shape(x,y)+self.drift_rate*self.th.clock)
        z=sorted(values)[len(values)//2]
        self.th.position[2]=values[-1]
        return self.th.position[:2]+[z]

class Mesh:
    def __init__(self):self.mesh='old';self.saved=[]
    def set_mesh(self,mesh):self.mesh=mesh
    def save_profile(self,name):self.saved.append(name)

class Calibrate(native.BedMeshCalibrate):
    # Use the unmodified vendor probe_finalize(), including XY ordering and
    # the actual ZMesh builder; only configuration/motion setup is simulated.
    def __init__(self,mesh,gcode,x_count=3,y_count=3):
        self.bedmesh=mesh;self.gcode=gcode;self.faulty_regions=[];self.radius=None
        self.substituted_indices={};self.relative_reference_index=None
        self.orig_config={'mesh_min':(20.,30.),'mesh_max':(395.,400.)}
        self.mesh_config={'x_count':x_count,'y_count':y_count,'mesh_x_pps':2,'mesh_y_pps':2,
            'algo':'lagrange' if max(x_count,y_count)<=6 else 'bicubic','tension':.2}
        self.probe_helper=types.SimpleNamespace(horizontal_move_z=3.,speed=200.) if hasattr(types,'SimpleNamespace') else Helper()
        self.points=[]
        for row in range(y_count):
            xs=list(range(x_count))
            if row%2:xs.reverse()
            self.points.extend([[200.+column*2.,200.+row*2.] for column in xs])
    def update_config(self,command):self.updated=True
    def _get_adjusted_points(self):return self.points

class Helper:
    horizontal_move_z=3.;speed=200.

class Printer:
    def __init__(self,x=3,y=3):
        self.toolhead=Toolhead();self.gcode=GCode();self.probe=Probe(self.toolhead);self.mesh=Mesh();self.mesh.bmc=Calibrate(self.mesh,self.gcode,x,y);self.events={}
    def get_reactor(self):return self
    def monotonic(self):return self.toolhead.clock
    def lookup_object(self,name,default=None):return {'toolhead':self.toolhead,'gcode':self.gcode,'probe':self.probe,'bed_mesh':self.mesh}.get(name,default)
    def register_event_handler(self,name,handler):self.events[name]=handler

class Config:
    error=RuntimeError
    def __init__(self,printer):self.printer=printer
    def get_printer(self):return self.printer
    def getfloatlist(self,name,default,**limits):return default
    def getfloat(self,name,default,**limits):return default
    def getint(self,name,default,**limits):return default

class Rail:
    def __init__(self,name):self.name=name
    def get_name(self):return self.name

class DriftTests(unittest.TestCase):
    def setup(self,x=3,y=3,homed=True):
        p=Printer(x,y);m=module.AdaptiveMeshDrift(Config(p))
        if homed:
            for axis in 'xyz':m.handle_home_end(None,[Rail('stepper_'+axis)])
        return p,m
    def test_interpolation_preserves_shape_with_integer_timestamps(self):
        samples=[(1,[10.,20.,.24]),(2,[30.,40.,.38])]
        corrected=module.correct_block(samples,(0,.1),(4,.26),.1)
        self.assertAlmostEqual(corrected[0][2],.2)
        self.assertAlmostEqual(corrected[1][2],.3)
        self.assertEqual(corrected[0][:2],[10.,20.])
    def test_invalid_and_unbracketed_data_rejected(self):
        for samples,previous,following in [([(5,[1,2,.3])],(0,.1),(4,.2)),
                                          ([(1,[1,2,float('nan')])],(0,.1),(4,.2)),
                                          ([(1,[1,2,.3])],(4,.1),(4,.2))]:
            with self.assertRaises(ValueError):module.correct_block(samples,previous,following,.1)
    def test_fake_touchscreen_home_is_insufficient(self):
        p,m=self.setup(homed=False)
        with self.assertRaises(RuntimeError):m.cmd_CALIBRATE(Command())
        self.assertEqual(p.toolhead.moves,[]);self.assertEqual(p.mesh.mesh,'old')
    def test_only_completed_rail_is_marked_and_motor_off_invalidates(self):
        p,m=self.setup(homed=False)
        m.handle_home_end(None,[Rail('stepper_x')]);self.assertEqual(m.real_homed,set((0,)))
        m.handle_home_end(None,[Rail('stepper_y'),Rail('stepper_z')]);self.assertEqual(m.real_homed,set((0,1,2)))
        m.handle_home_begin(None,[Rail('stepper_z')]);self.assertEqual(m.real_homed,set((0,1)))
        m.handle_motor_off(0);self.assertEqual(m.real_homed,set())
    def test_partial_final_group_and_true_vendor_matrix(self):
        p,m=self.setup();m.cmd_CALIBRATE(Command({'CONDITION_SECONDS':'0','PROFILE':'checked'}))
        run=m.last_run;self.assertTrue(run['valid']);self.assertEqual(run['completed_references'],2)
        self.assertEqual(len(run['raw_points']),9);self.assertEqual(len(run['corrected_points']),9)
        self.assertEqual([r['after_point'] for r in run['references']],[0,5,9])
        self.assertEqual(p.mesh.saved,['checked']);self.assertEqual(p.probe.begins,p.probe.ends)
        for point,raw in zip(run['corrected_points'],run['raw_points']):
            x=point[0]-24.25;y=point[1]+20.45
            self.assertAlmostEqual(point[2],Probe.shape(x,y)+run['baseline_z'],places=9)
            self.assertEqual(point[:2],raw['position'][:2])
        self.assertEqual(len(p.mesh.mesh.probed_matrix),3)
        self.assertTrue(all(len(row)==3 for row in p.mesh.mesh.probed_matrix))
    def test_ninety_mesh_points_get_eighteen_independent_references(self):
        p,m=self.setup(9,10);m.cmd_CALIBRATE(Command({'CONDITION_SECONDS':'0'}))
        self.assertEqual(m.last_run['completed_points'],90)
        self.assertEqual(m.last_run['completed_references'],18)
        self.assertEqual(len(p.probe.calls),109)
        self.assertTrue(all(c[2:]==(3,'median') for c in p.probe.calls))
        self.assertEqual(len(p.mesh.mesh.probed_matrix),10)
        self.assertTrue(all(len(row)==9 for row in p.mesh.mesh.probed_matrix))
    def test_three_minute_hold_uses_elapsed_time(self):
        p,m=self.setup();m.cmd_CALIBRATE(Command())
        self.assertTrue(180. <= m.last_run['actual_condition_seconds'] < 180.2)
        self.assertEqual(p.probe.calls[0][2],1)
        self.assertTrue(all(c[2]==3 for c in p.probe.calls[1:]))
    def test_probe_failure_does_not_save_or_leave_active_mesh(self):
        p,m=self.setup();p.probe.fail_at=7
        with self.assertRaises(RuntimeError):m.cmd_CALIBRATE(Command({'CONDITION_SECONDS':'0'}))
        self.assertFalse(m.last_run['valid']);self.assertFalse(m.running)
        self.assertEqual(p.probe.begins,p.probe.ends);self.assertIsNone(p.mesh.mesh);self.assertEqual(p.mesh.saved,[])
    def test_excessive_reference_drift_fails_closed(self):
        p,m=self.setup();m.max_drift=.001
        with self.assertRaises(RuntimeError):m.cmd_CALIBRATE(Command({'CONDITION_SECONDS':'0'}))
        self.assertIsNone(p.mesh.mesh);self.assertEqual(p.mesh.saved,[])
    def test_reference_outside_small_mesh_remains_independent(self):
        p,m=self.setup();p.mesh.bmc.points=[[30.+column,40.+row] for row in range(3) for column in (range(3) if row%2==0 else reversed(range(3)))]
        m.cmd_CALIBRATE(Command({'CONDITION_SECONDS':'0'}))
        self.assertEqual(p.probe.calls[0][:2],(215.,215.))
        self.assertTrue(all(point[0]<100 for point in m.last_run['corrected_points']))

if __name__=='__main__':unittest.main(verbosity=2)
