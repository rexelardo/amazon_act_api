import sys
import os
import logging
from io import StringIO
import contextlib
from fastapi import FastAPI, HTTPException
from nova_act import NovaAct
from dotenv import load_dotenv
import builtins
from typing import List, Dict, Any

load_dotenv()
app = FastAPI()

# Global variables
nova = None
captured_logs = []
captured_prints = []

class LogCapture(logging.Handler):
    """Custom logging handler to capture all log messages"""
    def __init__(self):
        super().__init__()
        self.logs = []
    
    def emit(self, record):
        self.logs.append({
            'level': record.levelname,
            'message': self.format(record),
            'timestamp': record.created
        })

# Global log capture instance
log_capture = LogCapture()

@contextlib.contextmanager
def capture_everything():
    """Capture stdout, stderr, logging, and print statements"""
    global captured_logs, captured_prints
    
    # Reset captures
    captured_logs = []
    captured_prints = []
    
    # Capture stdout/stderr
    old_stdout, old_stderr = sys.stdout, sys.stderr
    stdout, stderr = StringIO(), StringIO()
    
    # Capture print function
    original_print = builtins.print
    
    def custom_print(*args, **kwargs):
        message = ' '.join(str(arg) for arg in args)
        captured_prints.append(message)
        # Still print to captured stdout
        original_print(*args, file=stdout, **kwargs)
        # Also print to original stdout for debugging
        original_print(*args, file=old_stdout, **kwargs)
    
    # Setup logging capture
    root_logger = logging.getLogger()
    original_level = root_logger.level
    root_logger.setLevel(logging.DEBUG)
    root_logger.addHandler(log_capture)
    
    # Set environment variables for maximum verbosity
    os.environ['PYTHONUNBUFFERED'] = '1'
    os.environ['NOVA_ACT_DEBUG'] = '1'
    os.environ['NOVA_ACT_VERBOSE'] = '1'
    os.environ['AWS_LOG_LEVEL'] = 'DEBUG'
    
    try:
        sys.stdout, sys.stderr = stdout, stderr
        builtins.print = custom_print
        yield stdout, stderr
    finally:
        sys.stdout, sys.stderr = old_stdout, old_stderr
        builtins.print = original_print
        root_logger.removeHandler(log_capture)
        root_logger.setLevel(original_level)

@app.post("/start")
def start():
    global nova
    if nova is not None:
        return {"status": "already started"}
    
    with capture_everything() as (stdout, stderr):
        # Try different Nova Act initialization options for verbose output
        try:
            # Try with debug/verbose options if supported
            nova = NovaAct(
                starting_page="https://www.amazon.com", 
                headless=True,
                # Add potential debug options
                debug=True,
                verbose=True
            )
        except TypeError:
            # Fallback to basic initialization
            nova = NovaAct(starting_page="https://www.amazon.com", headless=True)
        
        nova.start()
    
    return {
        "status": "started",
        "stdout": stdout.getvalue(),
        "stderr": stderr.getvalue(),
        "logs": log_capture.logs.copy(),
        "prints": captured_prints.copy()
    }

@app.post("/act")
def act(query: str):
    global nova, captured_logs, captured_prints
    
    if nova is None:
        raise HTTPException(status_code=400, detail="Session not started")
    
    with capture_everything() as (stdout, stderr):
        # Clear previous captures
        log_capture.logs.clear()
        
        # Try to enable debugging on the nova instance if possible
        try:
            if hasattr(nova, 'set_debug'):
                nova.set_debug(True)
            if hasattr(nova, 'set_verbose'):
                nova.set_verbose(True)
        except:
            pass
        
        # Execute the action
        result = nova.act(query)
        
        # Try to get additional debug info from the result
        debug_info = {}
        if hasattr(result, '__dict__'):
            for key, value in result.__dict__.items():
                if not key.startswith('_'):
                    try:
                        if isinstance(value, (str, int, float, bool, list, dict)):
                            debug_info[key] = value
                    except:
                        pass
    
    # Check if result has any logging/step information
    step_info = []
    if hasattr(result, 'steps'):
        step_info = result.steps
    elif hasattr(result, 'trace'):
        step_info = result.trace
    elif hasattr(result, 'log'):
        step_info = result.log
    
    return {
        "result": result,
        "stdout": stdout.getvalue(),
        "stderr": stderr.getvalue(),
        "logs": log_capture.logs.copy(),
        "prints": captured_prints.copy(),
        "debug_info": debug_info,
        "step_info": step_info,
        "env_vars": {
            "PYTHONUNBUFFERED": os.environ.get('PYTHONUNBUFFERED'),
            "NOVA_ACT_DEBUG": os.environ.get('NOVA_ACT_DEBUG'),
            "NOVA_ACT_VERBOSE": os.environ.get('NOVA_ACT_VERBOSE')
        }
    }

@app.post("/get_session_info")
def get_session_info():
    """Get detailed information about the current Nova Act session"""
    global nova
    if nova is None:
        raise HTTPException(status_code=400, detail="Session not started")
    
    session_info = {}
    
    # Try to get session details
    try:
        if hasattr(nova, 'session_id'):
            session_info['session_id'] = nova.session_id
        if hasattr(nova, 'get_logs'):
            session_info['internal_logs'] = nova.get_logs()
        if hasattr(nova, 'get_history'):
            session_info['history'] = nova.get_history()
        if hasattr(nova, 'get_state'):
            session_info['state'] = nova.get_state()
        if hasattr(nova, '__dict__'):
            session_info['attributes'] = {k: v for k, v in nova.__dict__.items() 
                                        if not k.startswith('_') and isinstance(v, (str, int, float, bool, list, dict))}
    except Exception as e:
        session_info['error'] = str(e)
    
    return {"session_info": session_info}

@app.post("/stop")
def stop():
    global nova
    if nova is not None:
        with capture_everything() as (stdout, stderr):
            nova.stop()
            nova = None
        
        return {
            "status": "stopped",
            "stdout": stdout.getvalue(),
            "stderr": stderr.getvalue(),
            "logs": log_capture.logs.copy(),
            "prints": captured_prints.copy()
        }
    return {"status": "not running"}

# Alternative endpoint that tries to access Nova Act's internal logging
@app.post("/act_with_internal_logs")
def act_with_internal_logs(query: str):
    """Alternative approach that tries to access Nova Act's internal logging mechanisms"""
    global nova
    
    if nova is None:
        raise HTTPException(status_code=400, detail="Session not started")
    
    # Try to monkey patch Nova Act's internal methods
    original_methods = {}
    patched_calls = []
    
    try:
        # Try to find and patch common method names that might contain think() logic
        for method_name in ['_think', '_reason', '_plan', '_execute_step', '_log', 'think']:
            if hasattr(nova, method_name):
                original_method = getattr(nova, method_name)
                original_methods[method_name] = original_method
                
                def create_patched_method(orig_method, name):
                    def patched(*args, **kwargs):
                        patched_calls.append(f"Called {name} with args: {args[:2]}...")  # Truncate for safety
                        result = orig_method(*args, **kwargs)
                        patched_calls.append(f"{name} returned: {str(result)[:100]}...")  # Truncate for safety
                        return result
                    return patched
                
                setattr(nova, method_name, create_patched_method(original_method, method_name))
        
        # Execute the action
        result = nova.act(query)
        
    finally:
        # Restore original methods
        for method_name, original_method in original_methods.items():
            setattr(nova, method_name, original_method)
    
    return {
        "result": result,
        "patched_calls": patched_calls,
        "methods_found": list(original_methods.keys())
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)