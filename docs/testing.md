# Testing Guide

## Unit Tests

Test individual components in isolation:

```bash
pytest tests/test_agent_network.py::test_agent_factory_creation -v
```

## Integration Tests

Test full workflows with mocked LLMs:

```bash
pytest tests/ -v
```

## Performance Tests

Measure execution time across teams:

```python
import time
from agent_network import ParallelAgentNetwork

start = time.time()
# Execute workflow
results = await network.execute_parallel("test task")
elapsed = time.time() - start

print(f"Total time: {elapsed:.2f}s")
for r in results:
    print(f"  {r.team_name}: {r.duration:.2f}s")
```

## Debugging

### Enable verbose logging
```bash
export LOG_LEVEL=DEBUG
python main.py "task"
```

### Check agent messages
```python
results = await network.execute_parallel("task")
for r in results:
    if r.messages:
        for msg in r.messages:
            print(f"{msg['name']}: {msg['content'][:100]}...")
```

### Monitor HelixDB
```bash
# Check vector db status
python -c "import chromadb; c = chromadb.Client(); print(c.list_collections())"
```
