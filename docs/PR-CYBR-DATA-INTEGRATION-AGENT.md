**Assistant-ID**:
- `asst_NgkKNlJ9m8HrKZ07jB0AzKU8`

**Github Repository**:
- Repo: `https://github.com/PR-CYBR/PR-CYBR-DATA-INTEGRATION-AGENT`
- Setup Script (local): `https://github.com/PR-CYBR/PR-CYBR-DATA-INTEGRATION-AGENT/blob/main/scripts/local_setup.sh`
- Setup Script (cloud): `https://github.com/PR-CYBR/PR-CYBR-DATA-INTEGRATION-AGENT/blob/main/.github/workflows/docker-compose.yml`
- Project Board: `https://github.com/orgs/PR-CYBR/projects/7`
- Discussion Board: `https://github.com/PR-CYBR/PR-CYBR-DATA-INTEGRATION-AGENT/discussions`
- Wiki: `https://github.com/PR-CYBR/PR-CYBR-DATA-INTEGRATION-AGENT/wiki`

**Docker Repository**:
- Repo: `https://hub.docker.com/repository/docker/prcybr/pr-cybr-data-integration-agent`
- Pull-Command:
```shell
docker pull prcybr/pr-cybr-data-integration-agent
```


---

```markdown
# System Instructions for PR-CYBR-DATA-INTEGRATION-AGENT

## Role:
You are the `PR-CYBR-DATA-INTEGRATION-AGENT`, an AI agent responsible for managing, integrating, and optimizing data flows across all components of the PR-CYBR initiative. Your primary objective is to ensure seamless data interoperability, maintain data accuracy, and facilitate data-driven decision-making for all divisions, barrios, and sectors of the initiative.

## Core Functions:
1. **Data Integration**:
   - Aggregate, process, and normalize data from diverse sources (e.g., division-specific reports, agent outputs, external data feeds).
   - Ensure consistency and compatibility of data formats across all PR-CYBR systems.
   - Build and maintain pipelines to automate data ingestion, transformation, and storage.

2. **Data Management**:
   - Maintain a secure, organized, and scalable data repository for PR-CYBR.
   - Implement robust data validation and quality assurance processes.
   - Ensure data redundancy, backup, and disaster recovery mechanisms are in place.

3. **Analytics Support**:
   - Provide real-time insights and visualizations to assist in decision-making.
   - Enable data-driven strategies by supporting advanced analytics for other agents (e.g., Security, Performance).
   - Identify trends, patterns, and anomalies in data to enhance operational efficiency.

4. **Inter-Agent Collaboration**:
   - Act as the data backbone for all PR-CYBR agents, facilitating seamless data sharing and synchronization.
   - Enable inter-agent data requests, ensuring timely and accurate responses.
   - Maintain a record of all agent-related data interactions for transparency and accountability.

5. **Data Privacy and Security**:
   - Enforce strict data governance policies, ensuring compliance with ethical and legal standards.
   - Protect sensitive data with encryption, access controls, and monitoring for unauthorized activity.
   - Conduct regular audits to identify and mitigate data security vulnerabilities.

6. **Data Enrichment**:
   - Enhance raw data by incorporating metadata, geospatial tagging, or external context where applicable.
   - Use AI/ML models to extract actionable insights and augment datasets.
   - Assist in generating division-specific reports and dashboards with enriched, meaningful data.

## Key Directives:
- Ensure all data handled is accurate, relevant, and up-to-date.
- Facilitate data-driven workflows by integrating insights into PR-CYBR’s broader mission.
- Optimize the flow of information to reduce delays and improve decision-making.
- Support the long-term scalability of PR-CYBR’s data infrastructure as the initiative grows.

## Interaction Guidelines:
- Respond to queries with clear, concise, and actionable data outputs.
- Anticipate the data needs of other agents and proactively address them.
- Communicate technical concepts in accessible language for the user while maintaining precision.
- Provide visualizations, graphs, or reports when applicable to enhance understanding.

## Context Awareness:
- Maintain a holistic understanding of PR-CYBR’s mission, structure, and operational goals.
- Leverage historical data, uploaded documentation, and ongoing developments to provide relevant insights.
- Align all data-related activities with PR-CYBR’s vision of enhancing cybersecurity resilience across Puerto Rico.

## Tools and Integration:
You are equipped with advanced data processing capabilities, access to PR-CYBR’s centralized data repositories, and APIs for external data sources. Use these tools to automate workflows, maintain data integrity, and provide value to all agents and stakeholders.
```

**Directory Structure**:

```shell
PR-CYBR-DATA-INTEGRATION-AGENT/
	.github/
		workflows/
			ci-cd.yml
			docker-compose.yml
			openai-function.yml
	config/
		docker-compose.yml
		secrets.example.yml
		settings.yml
	docs/
		OPORD/
		README.md
	scripts/
		deploy_agent.sh
		local_setup.sh
		provision_agent.sh
	src/
		agent_logic/
			__init__.py
			core_functions.py
		shared/
			__init__.py
			utils.py
	tests/
		test_core_functions.py
	web/
		README.md
		index.html
	.gitignore
	LICENSE
	README.md
	requirements.txt
	setup.py
```

## Agent Core Functionality Overview

```markdown
# PR-CYBR-DATA-INTEGRATION-AGENT Core Functionality Technical Outline

## Introduction

The **PR-CYBR-DATA-INTEGRATION-AGENT** is responsible for managing, integrating, and optimizing data flows across all components of the PR-CYBR initiative. Its primary objective is to ensure seamless data interoperability, maintain data accuracy, and facilitate data-driven decision-making for all divisions, barrios, and sectors of the initiative.
```

```markdown
### Directory Structure

PR-CYBR-DATA-INTEGRATION-AGENT/
├── config/
│   ├── docker-compose.yml
│   ├── secrets.example.yml
│   └── settings.yml
├── scripts/
│   ├── deploy_agent.sh
│   ├── local_setup.sh
│   └── provision_agent.sh
├── src/
│   ├── agent_logic/
│   │   ├── __init__.py
│   │   └── core_functions.py
│   ├── data_pipelines/
│   │   ├── __init__.py
│   │   ├── ingestion.py
│   │   ├── transformation.py
│   │   └── validation.py
│   ├── shared/
│   │   ├── __init__.py
│   │   └── utils.py
│   └── interfaces/
│       ├── __init__.py
│       └── inter_agent_comm.py
├── tests/
│   ├── test_core_functions.py
│   ├── test_ingestion.py
│   └── test_transformation.py
└── web/
    ├── static/
    ├── templates/
    └── app.py
```

```markdown
## Key Files and Modules

- **`src/agent_logic/core_functions.py`**: Centralizes the main logic for data integration processes.
- **`src/data_pipelines/ingestion.py`**: Handles data ingestion from various sources.
- **`src/data_pipelines/transformation.py`**: Manages data normalization and transformation.
- **`src/data_pipelines/validation.py`**: Implements data validation and quality checks.
- **`src/shared/utils.py`**: Contains utility functions shared across modules.
- **`src/interfaces/inter_agent_comm.py`**: Facilitates communication with other agents.

## Core Functionalities

### 1. Data Ingestion (`ingestion.py`)

#### Modules and Functions:

- **`ingest_from_sources()`**
  - Inputs: Source configurations from `settings.yml`.
  - Processes: Connects to various data sources (APIs, databases, filesystems) to retrieve data.
  - Outputs: Raw data stored temporarily for processing.

- **`schedule_ingestion_jobs()`**
  - Inputs: Ingestion schedules and intervals.
  - Processes: Uses schedulers like APScheduler to automate data fetching.
  - Outputs: Timely execution of data ingestion tasks.

#### Interaction with Other Agents:

- **Data Requests**: Receives data requests from `PR-CYBR-MGMT-AGENT` for specific datasets.
- **Notifications**: Informs `PR-CYBR-DATABASE-AGENT` when new data is available for storage.

### 2. Data Transformation (`transformation.py`)

#### Modules and Functions:

- **`normalize_data()`**
  - Inputs: Raw data from ingestion.
  - Processes: Converts data into standardized formats and structures.
  - Outputs: Normalized data ready for validation.

- **`enrich_data()`**
  - Inputs: Normalized data, external datasets.
  - Processes: Enhances data by adding context or metadata.
  - Outputs: Enriched datasets for analysis.

#### Interaction with Other Agents:

- **Data Standards**: Aligns with `PR-CYBR-DATABASE-AGENT` on data schemas.
- **Analytics Support**: Provides clean data to `PR-CYBR-PERFORMANCE-AGENT` and `PR-CYBR-SECURITY-AGENT` for analysis.

### 3. Data Validation (`validation.py`)

#### Modules and Functions:

- **`validate_schema()`**
  - Inputs: Data schemas from `settings.yml`, transformed data.
  - Processes: Checks data conformity to predefined schemas.
  - Outputs: Validation reports, flags invalid records.

- **`quality_checks()`**
  - Inputs: Validation rules, data thresholds.
  - Processes: Performs checks like null value detection, duplication, and range validation.
  - Outputs: Cleaned data and quality metrics.

#### Interaction with Other Agents:

- **Error Reporting**: Sends validation errors to `PR-CYBR-MGMT-AGENT` for oversight.
- **Data Correction**: Works with data providers to correct issues.

### 4. Data Integration (`core_functions.py`)

#### Modules and Functions:

- **`integrate_data()`**
  - Inputs: Validated data from pipelines.
  - Processes: Merges datasets, resolves conflicts, and ensures data consistency.
  - Outputs: Integrated datasets stored in the data repository.

- **`manage_data_pipelines()`**
  - Inputs: Pipeline configurations.
  - Processes: Orchestrates the execution of ingestion, transformation, and validation modules.
  - Outputs: Smooth operation of data pipelines.

#### Interaction with Other Agents:

- **Data Distribution**: Provides integrated data to agents like `PR-CYBR-FRONTEND-AGENT` and `PR-CYBR-BACKEND-AGENT`.
- **Updates**: Notifies `PR-CYBR-USER-FEEDBACK-AGENT` when new data impacts user-facing features.

### 5. Data Management (`utils.py` and `inter_agent_comm.py`)

#### Modules and Functions:

- **`secure_data_transfer()`** (`utils.py`)
  - Implements encryption protocols for data at rest and in transit.

- **`log_data_activity()`** (`utils.py`)
  - Logs data operations for auditing and compliance.

- **`send_data()` / `receive_data()`** (`inter_agent_comm.py`)
  - Handles data requests and responses between agents.

#### Interaction with Other Agents:

- **Compliance**: Ensures data handling meets standards set by `PR-CYBR-SECURITY-AGENT`.
- **Data Access**: Provides APIs for data access by other agents.

## Inter-Agent Communication Mechanisms

### Communication Protocols

- **RESTful APIs**: Exposes endpoints for data requests and submissions.
- **gRPC**: For efficient, high-performance communication where necessary.
- **Message Queues**: Uses systems like Kafka for streaming data to agents that require real-time updates.

### Data Formats

- **JSON and XML**: For standard data interchange.
- **CSV and Parquet**: For bulk data transfers.

### Authentication and Authorization

- **API Keys and Tokens**: Secured and managed for inter-agent API access.
- **Access Control Lists (ACLs)**: Define permissions for data access.

## Interaction with Specific Agents

### PR-CYBR-DATABASE-AGENT

- **Data Storage**: Sends integrated and validated data for persistent storage.
- **Schema Alignment**: Collaborates on data schema definitions and updates.

### PR-CYBR-PERFORMANCE-AGENT

- **Data Provisioning**: Supplies performance metrics and logs for analysis.
- **Real-time Data**: Streams data required for live performance monitoring.

### PR-CYBR-SECURITY-AGENT

- **Anomaly Detection**: Shares data patterns that may indicate security threats.
- **Secure Data Handling**: Implements security protocols defined by this agent.

## Technical Workflows

### Data Pipeline Workflow

1. **Ingestion**: `ingest_from_sources()` fetches data according to schedule.
2. **Transformation**: `normalize_data()` and `enrich_data()` process raw data.
3. **Validation**: `validate_schema()` and `quality_checks()` ensure data integrity.
4. **Integration**: `integrate_data()` merges data into unified datasets.
5. **Distribution**: Data is stored and made accessible to other agents.

### Real-time Data Streaming

- **Setup**: Configured for sources requiring real-time updates.
- **Processing**: Uses streaming platforms like Apache Kafka or Apache Flink.
- **Consumption**: Agents subscribe to data streams as needed.

## Database and Storage

- **Temporary Storage**: Uses in-memory databases (e.g., Redis) during processing.
- **Persistent Storage**: Integrated with `PR-CYBR-DATABASE-AGENT` for long-term storage.
- **Data Lake**: Manages a data lake for unstructured or semi-structured data.

## Error Handling and Logging

- **Logging**: Comprehensive logging of data pipeline activities.
- **Error Notifications**: Alerts sent to `PR-CYBR-MGMT-AGENT` and relevant agents when issues arise.
- **Retry Mechanisms**: Automatic retries for transient failures during data ingestion.

## Security Considerations

- **Data Encryption**: Encrypts sensitive data fields.
- **Access Controls**: Implements role-based access controls (RBAC).
- **Compliance**: Ensures data handling complies with data protection regulations.

## Deployment and Scaling

- **Containerization**: Dockerized services for each component of the data pipeline.
- **Orchestration**: Uses Kubernetes for scaling and managing containers.
- **Scalability**: Supports horizontal scaling to handle increasing data volumes.

## Conclusion

The **PR-CYBR-DATA-INTEGRATION-AGENT** plays a critical role in ensuring that accurate and timely data flows through the PR-CYBR ecosystem. By leveraging robust data pipelines, validation mechanisms, and inter-agent communication protocols, it provides a solid foundation for data-driven operations and decision-making across the initiative.
```


---

## OpenAI Functions

## Function List for PR-CYBR-DATA-INTEGRATION-AGENT

```markdown
## Function List for PR-CYBR-DATA-INTEGRATION-AGENT

1. **aggregate_data_sources**: Collects and normalizes data from multiple sources into a unified format to ensure consistent data quality across PR-CYBR initiatives.
2. **validate_data_integrity**: Performs checks and validations on incoming data to ensure accuracy, relevance, and timeliness, flagging any discrepancies for review.
3. **generate_real_time_insights**: Provides analytics and visualizations from the current data repository, enabling agile decision-making and operational efficiency.
4. ** facilitate_data_sharing**: Streamlines the process for inter-agent data requests, ensuring timely and accurate exchanges of information between PR-CYBR agents.
5. **track_data_access**: Monitors and records access to sensitive data to ensure compliance with data governance policies and mitigate potential security risks.
6. **automate_data_backup**: Sets up scheduled backups for data repositories to prevent loss of critical information and ensure disaster recovery readiness.
7. **support_advanced_analytics**: Provides necessary datasets and analytical support for other agents to conduct advanced data analysis and develop insights-driven strategies.
8. **deploy_data_enrichment**: Enriches raw data with contextual and metadata enhancements, improving the quality and usability of datasets for analysis.
9. **create_dashboard_reports**: Develops comprehensive reports and dashboards tailored for different divisions, enhancing visibility into key performance metrics.
10. **enable_user_interaction**: Powers the Agent Dashboard Chat functionality, allowing human users to interact, query, and receive insights from the agent in real-time.
```