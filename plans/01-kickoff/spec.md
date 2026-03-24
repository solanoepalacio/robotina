# Robotina
## Project Overview:
Robotina is a home assistant helping families organize their recipes, meal plan, groceries stock and other useful tasks for households.

Robotina is a component of a slightly bigger system that comprises 3 components:
- A user application (client)
- A backend service
- Robotina
> This repository deals specifically with "Robotina" component

The source of truth of household data in the system is the "backend" component.
Users can use the application to consult and edit their household information manually (recipes, meal plan, etc...)
Users can also talk to Robotina so that robotina does this on their behalf.
Robotina has access to read and modify household information on their behalf.

Robotina inner workings is described by four areas:
- triggers: telegram + scheduled tasks
- context: what's injected into the model every time
- abilities: tools and skills the agent can use (often produce side effects)
- output: results of each task performed

In it's core Robotina works as a tasks queue. When a complex task arrives, Robotina will split it into multiple simple tasks, each of which is small enough that can be solved by a specialized agent in a single run.

### Triggers
To ensure that the agent process is executed with concurrency exactly equal to one, the agent is triggered by exactly one task queue (agent-task-queue), which acts as a multiplexer for work comming from different sources.
The possible sources of agent tasks are:
- User messages: user can write to the agent asking questions or delegating tasks. Multiple chat clients may be used. All incomming communications will be centralized by the "gateway" component described on the Tech Spec. User messages are not processed immediately, instead they enqueued for the agent to process when available.
- Scheduled tasks: The agent or application maintainers can create scheduled tasks. The agent doesn't process this tasks directly; instead the tasks are enqueued in the agent-task-queue for the agent to process when available.
- Agent created tasks: The agent itself may push a task to the agent-task-queue to perform a task as soon as possible.

### Context
The context the agent gets injected at each turn is dynamic and depends on the task type.
For example: An "incomming-user-message" task type may receive the user chat history, while a "research-recipe" task type may receive information about the recipe.

### Abilities
The agent has two ways to interact with its environment: Skills and Tools.

Skills: These are markdown files that instruct the agent how to achieve tasks. They are broken down into small chunks the agent can load as needed to avoid context bloat. Different skills will be required for different tasks. For closed end tasks the agent will get a hint at what skills will be needed to perform the task.

Tools: Regular agent tools allowing the agent to perform actions by calling code. They will be used to interact with the queue, the scheduler and external apis. Different tools will be required by different task types and should be loaded dynamically based on the task type.

### Output
All agent runs produce an output which should be persisted along with the completed task status (success or failure) on the agent-task-queue.
Only some agent runs may produce an output message to the user.
Some runs will only side effects by writting data to the backend, creating a schedule tasks or queueing a subsequent task.

## Scope:
This document describes the features to be implemented for **Phase 1** of Robotina.
It needs to covers two user stories:
- as a user I want to ask robotina questions in natural language about my household and get intelligent responses back based on the information stored on household-manager backend.
- as a user I want to ask robotina to research a recipe and eventually see that the recipe was added to my household recipes

To achieve this workflows we'll create:

1. Three Agents:
    - Robotina: Handles receiving and answering telegram messages. Has read access to the household-manager api to read and answer user questions.
    - Recipe Researcher: Handles researching recipes online
    - Recipe Loader: handles loading a recipe into household-manager backend.
2. Four task types:
    - handle-incomming-message
    - recipe-research
    - recipe-load
    - send-notification
3. Three task specific skills:
    - recipe-research
    - recipe-load
    - format-message


The workflow for the first user story (user message) looks like this:
```
user writes a message -> gateway -> task (handle-incomming-message) -> skill (household manager) -> skill (format message) -> reply sent to user
```

The workflow for the second user story (recipe research) looks like this:
```
user asks to research or add a recipe -> task (handle-incomming-message) -> tool-call (queue new tasks) -> task (recipe-research) -> task (recipe-load) -> task (send notification) -> skill (format message) -> message sent to user letting him know that the recipe was added to the household
```

## Tech Spec:
Comprised of the following components:
- gateway
- scheduler
- queue
- agent
- LLM

### Diagrams:
- [Layers Diagram](./layers.png)
- [Components Diagram](./components.png)

### Gateway
Gateway component centralises the messages incoming from different messaging platforms and abstract away from the agent the details of handling communication (loading chat history, understanding message channels, etc).
On a first iteration only telegram will be integrated using a telegram bot.
Messages don't trigger the orchestrator directly, instead they are queued in the agent-task-queue.

### Scheduler
A standalone scheduling service capable of producing tasks. When a schedule tasks run it doesn't invoke the agent process directly, instead it writes to the agent-task-queue.
Tasks can be added to the scheduler in two ways:
- Agent can add scheduled tasks using a tool
- Other clients may add scheduled tasks using an api

### Queue
The queue represents the work pending to be done by the agent.
The agent reads from the queue and consumes it sequentially (concurrency exactly 1).
Each task consumed from the queue by the agent is considered "an agent run".
The agent may decide, based on the task, to enqueue a new task at the back or front of the queue.
Tasks in the queue must be easy to inspect by developers to understand when they have been executed, what was their input and output.
Each task has the following properties:
- a type
- an input
- an addition date
- a completion date
- a status (queued | processing | completed)
- a result status (null, success, failure)
- an output
Tasks inputs and outputs are strongly typed.

### Agent
Every time a task is taken from the queue, an agent is spawned to process it. We call the process consuming the queue and spawning the agent "task-runner".
The task runner acts like a wrapper around the agent run and is in charge of updating the task status, result status and output.
Task runner is also responsible for catching errors from the agent and handle them. Errors can be handled by creating a new task in the queue or by sending them to a dead letter queue for developer inspection.
Before spawning the agent the task runner uses the information on the files `agents.json` to determine, based on the task type, the following:
- what LLM provider and model will be used for the agent
- what system prompt and context is injected to the agent
- what tools are given to the agent
- what skills are loaded into the agent
- what prompt the agent gets
The values for each of these is configured by the developer using a json file (`agents.json`) that could look like (values are exemples, not exhaustive):
```json
[
    {
        "type": "research-recipe",
        "model": { "baseUrl": "", "apiToken": "", "model": "" },
        "prompt": "./research-recipe/v002.txt",
        "tools": ["web-search", "household-manager-api"],
        "skills": ["household-manager", "research-recipe""]
    }
]
```
The agent of the above example would be able to handle a "research-recipe" type task, using as system-prompt the text file at `robotina/src/agent/prompts/research-recipe/v002.txt`.

The developer must have the ability to override the file the configuration is taking from by passing in a `AGENTS_DEFINITION_FILEPATH` environment variable. This feature will be crucial for experimentation, evaluation and scenarios simulation.


#### LLM Backend:
The LLM backend configuration of any task should comprise the full connection details (two different agents runs may connect to different ollama instances, so simply configuring "ollama" is not enough. Connection configuration needs to contain connection url, model, token, etc.)

#### Context & System prompt:
Since the system breaks tasks into their smallest possible form, system prompts are crafted with one specific goal in mind: solve the task type they are associated with.

Prompts are versioned and old versions are kept around for history and analysis.

The fact that the system prompt is configured in `AGENTS_DEFINITION_FILEPATH` per task can be used to evaluate and iterate on the prompts and for quick regression in case degradation on the agent performance is detected after release.

When a skill is needed for a certain task the skill index it will be pre-loaded into the agent context.

For closed end tasks that can be solved with specific instructions the system prompt may make a direct mention of a skill the agent should use.

Tools are also loaded into the agent context based on the specific tools the agent will need to perform a certain task.

#### Tools:
Tools should be written in a composable manner such that different sets of tools can be loaded into different agent runs.
When the agent calls a tool that throws an error the agent can recover from the error by understanding the mistake and trying again with new parameters or even different tools.

The following tools will be essential for phase 1:
- household-manager api: a tool that the agent can use to call the recipe-manager api. It must handle authentication and error codes on behalf of the agent.
- read-skill: Allos the agent can use to read skills. Reads from `robotina/agent/skills/...`.
- web-search: Allows the agent to search the internet using Tavily api.
- scheduler: Allows the agent to CRUD scheduled jobs.

#### Skills:
Skills are markdown files that contain precise instructions to solve particular tasks.
For example:
- recipe-research: contains details instructions on how to search for a recipe on multiple internet sites and summarize the information from all sites
- format-message: contains details of how to structure and format a message for proper formatting on telegram.

One particularly relevant skill for this project is the "household-manager" skill, which tells the agent how to interact with the backend of the household-manager application to CRUD household information on behalf of the user. This skill is already implemented on `robotina/agent/skills/household-manager/*`. Based on requirements we must make some changes around how authentication is handled (should be handled by the tool and not by the agent).

### LLM
LLM module is a protocol abstracting the connection to LLM backends to allow the agents to easily swap between different module providers.
From the get go support for the following providers:
- ollama
- anthropic
- openai

## Non functional Requirements:
- System prompts should be written in markdown and versioned.
- All changes on the queue state are logged to console (new task queued, processing new task, task finished...)
- All actions performed by the agent are logged (llm start streaming, tool calls...)
- Debug log level can be enabled for each module independently (gateway, scheduler, queue, agent, LLM)
- Agents are implemented using Langchain.
- Agents should be carefully instrumented using LangWatch
- each agent or agentic workflow should have a langwatch experiment associated with it

## Draft Project Structure:
```
robotina/
├── plans/
│   └── 01-kickoff/
├── agent-workspace/
|   └── memories/
|       ├── household.md
|       ├── food-preferences.md
|       ├── meal-plan-preferences.md
|       └── household-members.md
├── src/
|   ├── llm/
|   ├── agent/
|   |   ├── agent.py
|   |   ├── agents.json
|   |   ├── prompts/
|   |   |    ├── robotina
|   |   |    |   ├── V001.txt
|   |   |    |   └── V002.txt
|   |   |    └── research-recipe
|   |   |        ├── V001.txt
|   |   |        └── V002.txt
|   |   ├── skills/
|   |   |   ├── format-telegram-message/
|   |   |   ├── research-recipe/
|   |   |   |   └── ...
|   |   |   └── household-manager/
|   |   |       └── ...
|   |   └── tools/
|   |       ├── scheduler
|   |       ├── web-search (tavily)
|   |       └── household-manager
|   ├── queue/
|   ├── gateway/
|   └── scheduler/
├── experiments/
|   └── one experiment per skill/...
├── scenarios/
|   └── multiple scenarios per prompt/...
├── tests/
|   └── ...
├── README.md
└── pyproject.toml
```

## Development phases:

- Gateway infrastructure
- Agent Queue
- Agent Infrastructure (prompt loading, agents.json, instrumentation, experiments...)
- "Robotina" Task and Agent -- Handles telegram messages
- "Recipe Research" Task and Agent -- handles recipe research
- scheduler



