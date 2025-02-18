# Debugging agents

The simplest tools for debugging are using the debug levels in the REPL:
    
    'agents' - Log agent operations
    'tools'  - Log all tool calls
    'llm'    - Log LLM completions
    'all'    - Log everything

Note that you can also combine tags like 'tools,llm':

```
> .debug tools,llm
Debug level set to: tools,llm
```

**Switching models**

Use `.model <model>` to temporarily change the active model of the current agent:

```
[Basic Agent]