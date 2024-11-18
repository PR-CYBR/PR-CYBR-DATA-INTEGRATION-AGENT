# General Operations Order (OPRORD) for PR-CYBR Agent Function Development

## Objective
Each PR-CYBR Agent is tasked with defining three key lists of functions to establish inter-agent operability and robust system design. This ensures consistent communication and actionable integration between agents in the ecosystem. Additionally, agents must define the structure of their Agent Dashboard and highlight key features of its UI/UX.

### Key Deliverables
1. **Core Application Functions**: Functions critical for the agent's primary operation.
2. **OpenAI Functions**: Functions leveraging OpenAI capabilities to enhance the agent's performance.
3. **PR-CYBR-Agent Functions**: Functions required to interact and communicate with other agents.
4. **Agent Dashboard Structure**: Define the layout and components of the agent's dashboard.
5. **Dashboard UI/UX Features**: Highlight key features and design elements of the dashboard's user interface and experience.

---

## Tasks and Guidelines

### 1. Core Application Functions

<!--
Key Point's to highlight about Agent Core Application Functions:

1. Functions needed for Agent Dashboard (frontend)
2. Functions needed for Agent Database (backend)
3. Functions needed for Agent Functions (core, openai, and pr-cybr-agent specific)
4. Functions needed for Setup / Installation (whether installng locally, via cloud, or in/with a CI/CD pipeline)
5. Functions needed for Security and Compliance
6. Functions needed for User Support and Feedback
7. Functions needed for Performance and Scalability
8. Functions needed for Reporting and Analytics
9. Functions needed for Integration with External Systems
10. Functions needed for Continuous Improvement and Updates
-->

- **Definition**: Functions that handle operational aspects specific to the agent's application, such as managing data, interfacing with the frontend or backend, and executing agent-specific tasks.
- **Examples**:
  - Querying and retrieving agent-specific data.
  - Performing task coordination.
  - Monitoring performance or status updates.

### 2. OpenAI Functions

<!--
Key Points to Highlight about Agent OpenAI Functions:

1. Extend the Agent's functionality (by utilizing function calling)
2. Allow the Agent to retrieve data stored in Vector Store (shared by all agents' AI Assistants)
3. Allow cross-platform actions (such as returning a response via Discord or Slack)
4. Allow for more advanced automation workflows (such as utilizing Zapier)
5. Enable the ability to trigger GitHub Actions (.yml workflow files / scripts)
6. Facilitate the ability for advanced web searching
7. Enhance Natural Language Processing capabilities
8. Support real-time language translation
9. Provide sentiment analysis for user feedback
10. Enable personalized content recommendations
11. Automate routine data analysis tasks
12. Integrate with cloud-based AI services
-->

- **Definition**: Functions implemented on OpenAI’s platform that extend the AI assistant's capabilities for tasks such as NLP, data analysis, or decision support.
- **Examples**:
  - Analyzing data for actionable insights.
  - Responding to user queries in natural language.
  - Generating strategic recommendations based on input.

### 3. PR-CYBR-Agent Functions

<!--
Key Points to Highlight about PR-CYBR-AGENT Functions:

1. Allow Agents to create new threads / add other Agents to current threads
2. Add data to threads
3. Prompt other Agents for their response
4. Utilize other Agents' functions (core, openai, and pr-cybr-agent specific)
5. Facilitate inter-agent data synchronization
6. Enable collaborative task execution
7. Support inter-agent alert and notification systems
8. Manage shared resource access and allocation
9. Coordinate multi-agent incident response
10. Implement inter-agent performance monitoring
-->

- **Definition**: Functions that facilitate communication and interaction between agents. These functions ensure smooth data flow, inter-agent task execution, and shared resource management.
- **Examples**:
  - Retrieving or pushing data to/from another agent.
  - Coordinating multi-agent responses to a system event.
  - Querying other agents for additional functionalities.

### 4. Agent Dashboard Structure

<!--
Key Point's to highlight about Agent Dashboard Structure:

1. Each Agent Dashboard should be unique to that Agent (meaning the layout of options will be different for each agent, however the main focal point / application is still the interactive map)
2. Each Agent Dashboard should contain the following menu bar:
    - DASH (this will function like a Home Page, where the user will see a list of avaliable agents (and their current status), a widget / preview of the Map Page, and a news feed with the latest cybersecurity news)
    - MAP (an interactive map, centered over Puerto Rico, using the theme choosen by the user)
    - AGENTS (a page that lists all PR-CYBR-AGENTS, along with a brief description for each)
    - ABOUT (this will provide an overview of PR-CYBR, a Mission Statement, breif overview of PR-CYBR-AGENTS, and links to: Github Organization, that particular Agent's specific links)
3. MAP: allow's the user to build maps with custom markers 
-->

- **Definition**: The layout and components of the agent's dashboard, providing a visual interface for users to interact with the agent's functionalities.
- **Examples**:
  - Overview panel displaying key metrics and status updates.
  - Interactive map for visualizing data and operations.
  - Task management section for assigning and tracking tasks.

### 5. Dashboard UI/UX Features

<!--
Key Point's to highlight about Agent Dashboard UI/UX:

1. Dashboard should be rendered with the user choosen theme 
2. Dashboard should load / autoplay music 
3. Dashboard should look and feel great whether viewing on computer or mobile device
4. Dashboard must be quick  and responsive
5. Has a map builder to allow for the user to create custom maps, with user specified markers
6. User should be able to export ther custom map 
-->

- **Definition**: Key features and design elements that enhance the user interface and experience of the dashboard.
- **Examples**:
  - Intuitive navigation with clear labeling and accessible menus.
  - Real-time data visualization with interactive charts and graphs.
  - Customizable widgets and layouts to suit user preferences.

---

## Submission Format
Each agent must provide their lists in separate markdown code blocks. The structure for each list is outlined below:

### Example:

`Core Application Functions`:
```markdown
## Core Application Functions
1. **function_name_1**
   - **Description**: Brief explanation of what this function does.
   - **Inputs**: Specify input parameters.
   - **Outputs**: Specify expected outputs.

2. **function_name_2**
   - **Description**: [Add details].
```


`OpenAI Functions`: 
```markdown
## OpenAI Functions
1. **function_name_1**
   - **Description**: [Add details].
   - **Inputs**: [Add details].
   - **Outputs**: [Add details].
```


`PR-CYBR-Agent Functions`:
```markdown
## PR-CYBR-Agent Functions
1. **function_name_1**
   - **Description**: [Add details].
   - **Purpose**: Define why this function is necessary for inter-agent communication.
   - **Inputs**: [Add details].
   - **Outputs**: [Add details].
```


`Agent Dashboard Structure`:
```markdown
## Agent Dashboard Structure
1. **Overview Panel**
   - **Description**: Displays key metrics and status updates.
   - **Components**: [Add details].

2. **Interactive Map**
   - **Description**: Visualizes data and operations.
   - **Components**: [Add details].
```


`Dashboard UI/UX Features`:
```markdown
## Dashboard UI/UX Features
1. **Intuitive Navigation**
   - **Description**: Provides clear labeling and accessible menus.
   - **Features**: [Add details].

2. **Real-Time Data Visualization**
   - **Description**: Interactive charts and graphs.
   - **Features**: [Add details].
```

## Notes for Execution

	•	Reference the Agent Overview Document and existing materials for context.
	•	Ensure function names and descriptions are concise and precise.
	•	Highlight how these functions align with the PR-CYBR mission and technical framework.
	•	Consider user feedback and usability principles when designing the dashboard.

---

**End of OPRORD**
