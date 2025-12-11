# Isolated Python Execution Service Guide

This guide explains the new **Isolated Python Execution Service** - a containerized solution that completely isolates Python code execution from the main PaleoPal application, solving multiprocessing issues and providing better security.

## 🎯 Problem Solved

**Before**: Scientific libraries like PyLiPD using multiprocessing caused massive service re-initialization, slow performance, and potential interference with the main application.

**After**: Complete process isolation in a dedicated container - no more multiprocessing interference, faster execution, and better security.

## 🏗️ Architecture

```
Main PaleoPal Backend    →    HTTP API    →    Isolated Execution Container
├── Agents                    ├── /execute           ├── Python + Scientific Libraries
├── Routers                   ├── /state             ├── State Management  
├── Services                  ├── /cancel            ├── Plot Generation
└── ExecutionClient           └── /health            └── Complete Isolation
```

## 🚀 Quick Start

### 1. Start the Isolated Execution Service

```bash
# Start just the execution service
docker-compose up execution-service

# Or start everything
docker-compose up
```

The service will be available at `http://localhost:8001`

### 2. Enable Isolated Execution (Optional)

Set environment variable to automatically use isolated execution:

```bash
export USE_ISOLATED_EXECUTION=true
```

Or in your `.env` file:
```
USE_ISOLATED_EXECUTION=true
```

### 3. Test the Service

```bash
# Run the test script
python test_isolated_execution.py
```

## 🔧 Usage Patterns

### Direct API Usage

```python
import requests

# Execute code via HTTP API
response = requests.post("http://localhost:8001/execute", json={
    "code": "import numpy as np\nresult = np.array([1,2,3]).sum()\nprint(f'Sum: {result}')",
    "conversation_id": "my_conversation",
    "execution_id": "exec_001"
})

result = response.json()
print(f"Success: {result['success']}")
print(f"Output: {result['output']}")
print(f"Variables: {result['variables']}")
```

### Using ExecutionClient (Recommended)

```python
from services.execution_client import ExecutionClient

# Create client
client = ExecutionClient("http://localhost:8001")

# Execute code
result = client.execute_code(
    code="import pandas as pd\ndf = pd.DataFrame({'a': [1,2,3]})\nprint(df)",
    conversation_id="my_conversation"
)

if result.success:
    print("Execution successful!")
    print(f"Output: {result.output}")
    print(f"Variables: {list(result.variables.keys())}")
else:
    print(f"Execution failed: {result.error}")
```

### Drop-in Replacement for AsyncExecutionService

```python
# OLD CODE (using AsyncExecutionService)
from services.async_execution_service import async_execution_service
result = async_execution_service.execute_code(code, conversation_id)

# NEW CODE (using ExecutionClient with same interface)
from services.execution_client import get_execution_client
execution_service = get_execution_client()
result = execution_service.execute_code(code, conversation_id)
```

## 📊 State Management

The isolated service maintains persistent state across executions:

```python
# First execution - create variables
client.execute_code(
    code="my_data = [1, 2, 3, 4, 5]\nmy_sum = sum(my_data)",
    conversation_id="conv_1"
)

# Second execution - use previous variables
result = client.execute_code(
    code="print(f'Previous sum: {my_sum}')\nmy_data.append(6)\nprint(f'New data: {my_data}')",
    conversation_id="conv_1"  # Same conversation ID
)
```

### State Operations

```python
# Get conversation state
state = client.get_conversation_state("conv_1")
print(f"Variables: {list(state.keys())}")

# Clear conversation state
client.clear_conversation_state("conv_1")

# Get service statistics
stats = client.get_state_statistics()
print(f"Active executions: {stats['active_executions']}")
```

## 🧪 Scientific Libraries Support

The isolated service includes all major scientific libraries:

```python
code = """
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import scipy.stats as stats
import pylipd
import pyleoclim as pyleo

# All libraries work without multiprocessing issues!
data = np.random.normal(0, 1, 1000)
df = pd.DataFrame({'values': data})

# Plots are automatically saved
plt.figure()
plt.hist(data, bins=30)
plt.title("Test Plot")
plt.show()  # This saves the plot automatically

print("All libraries loaded successfully!")
"""

result = client.execute_code(code, "science_test")
print(f"Plots generated: {result.plots}")
```

## 🔄 Async Execution

```python
import uuid

def update_callback(update):
    print(f"Status: {update['status']}")
    if update['status'] == 'completed':
        print(f"Output: {update['output']}")

# Submit async execution
execution_id = str(uuid.uuid4())
client.submit_execution(
    code="import time\ntime.sleep(2)\nprint('Async execution complete!')",
    conversation_id="async_test",
    execution_id=execution_id,
    update_callback=update_callback
)

# Check active executions
active = client.get_active_executions()
print(f"Active executions: {list(active.keys())}")

# Cancel if needed
client.cancel_execution(execution_id)
```

## 🐳 Docker Configuration

### Isolated Execution Service Container

The service runs in its own container with:

- **Base**: Python 3.11 slim
- **Libraries**: All scientific libraries (NumPy, Pandas, PyLiPD, PyLeoClim, etc.)
- **Isolation**: Complete process isolation
- **Persistence**: State and plots saved to Docker volumes
- **Health Checks**: Built-in health monitoring

### Volumes

- `execution-data`: Persistent state and plot storage
- Shared with main backend for plot access

### Environment Variables

- `TOKENIZERS_PARALLELISM=false`: Prevents tokenizer warnings
- `PYTHONUNBUFFERED=1`: Ensures real-time output

## 🔧 Integration with Existing Code

### Minimal Changes Required

1. **Import change**:
   ```python
   # OLD
   from services.async_execution_service import async_execution_service
   
   # NEW  
   from services.execution_client import get_execution_client
   execution_service = get_execution_client()
   ```

2. **Environment variable** (optional):
   ```bash
   USE_ISOLATED_EXECUTION=true
   ```

3. **Service Manager** (automatic):
   ```python
   # ServiceManager automatically uses isolated execution when enabled
   execution_service = service_manager.get_execution_service()
   ```

### Agent Integration

Agents can use the isolated service transparently:

```python
# In agent handlers
from services.service_manager import service_manager

def execute_code_node(state, config):
    execution_service = service_manager.get_execution_service()
    result = execution_service.execute_code(
        code=state.generated_code,
        conversation_id=state.conversation_id
    )
    # Rest of the code remains the same
```

## 🚨 Error Handling

```python
try:
    result = client.execute_code(code, conversation_id)
    if result.success:
        print("Success!")
    else:
        print(f"Execution error: {result.error}")
except requests.exceptions.ConnectionError:
    print("Cannot connect to isolated execution service")
    print("Make sure it's running: docker-compose up execution-service")
except requests.exceptions.Timeout:
    print("Execution timed out")
except Exception as e:
    print(f"Unexpected error: {e}")
```

## 📈 Performance Benefits

### Before (AsyncExecutionService)
- ❌ Multiprocessing spawns child processes
- ❌ Each child process re-initializes all services
- ❌ Massive memory usage and slow startup
- ❌ Potential interference between executions

### After (Isolated Execution Service)
- ✅ Complete process isolation
- ✅ No service re-initialization
- ✅ Fast execution (~0.5s vs 10s+)
- ✅ No interference between executions
- ✅ Better security and stability

## 🔒 Security Benefits

- **Process Isolation**: Code runs in separate container
- **Network Isolation**: Only HTTP API exposed
- **Resource Limits**: Container resource constraints
- **Code Validation**: AST-based safety checks
- **Restricted Imports**: Only allowed scientific libraries

## 🛠️ Troubleshooting

### Service Not Starting
```bash
# Check service status
docker-compose ps execution-service

# View logs
docker-compose logs execution-service

# Restart service
docker-compose restart execution-service
```

### Connection Issues
```bash
# Test health endpoint
curl http://localhost:8001/health

# Check port binding
docker-compose ps | grep 8001
```

### Execution Failures
```python
# Check service health
client = ExecutionClient()
if not client.health_check():
    print("Service is not healthy")

# Check service logs
docker-compose logs execution-service
```

## 🔮 Future Enhancements

- **Multi-container scaling**: Run multiple execution containers
- **Resource monitoring**: CPU/memory usage tracking  
- **Execution queuing**: Handle high-volume execution requests
- **Enhanced security**: Additional sandboxing options
- **WebSocket support**: Real-time execution streaming

## 📚 API Reference

### ExecutionClient Methods

- `execute_code(code, conversation_id, timeout=None, execution_id=None)`: Synchronous execution
- `submit_execution(code, conversation_id, execution_id, update_callback=None)`: Async execution  
- `cancel_execution(execution_id)`: Cancel running execution
- `get_conversation_state(conversation_id)`: Get state variables
- `clear_conversation_state(conversation_id)`: Clear state
- `get_active_executions()`: List active executions
- `get_state_statistics()`: Service statistics
- `health_check()`: Check service health

### HTTP API Endpoints

- `POST /execute`: Execute code synchronously
- `POST /execute/async`: Execute code asynchronously  
- `POST /cancel/{execution_id}`: Cancel execution
- `GET /state/{conversation_id}`: Get conversation state
- `DELETE /state/{conversation_id}`: Clear conversation state
- `GET /stats`: Service statistics
- `GET /health`: Health check

---

**The isolated execution service provides complete process isolation while maintaining the same interface as the original AsyncExecutionService. This solves multiprocessing issues and provides better performance, security, and stability.** 