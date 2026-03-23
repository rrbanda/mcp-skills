Admins build agents right from the Command Center -- no code, no YAML, just a form inside the admin console with a name, tools, and save

The system can generate instructions for you -- you describe what the agent should do in plain English, and it writes the full LLM prompt based on the tools you've configured

You can wire multiple agents together -- one agent can hand off a conversation to another, or delegate a task and get results back, all configured through dropdowns

Each agent gets its own set of tools -- admins pick which MCP servers, knowledge bases, web search, or code interpreter that specific agent can use

Everything is validated before you save -- the UI catches missing fields, broken references, and circular handoffs in real time so you don't deploy a broken configuration
