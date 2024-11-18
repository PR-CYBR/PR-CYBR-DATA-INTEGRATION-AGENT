# OPORD-0005: Mission Package Automation for PR-CYBR-AGENTS

## **1. SITUATION**
All PR-CYBR agents are tasked with providing users the capability to generate, manage, and deliver TAK Mission Packages efficiently and accurately. This operation requires automating form data handling, database updates, order assignment, and status tracking using tools such as Google Forms, Google Sheets, and automation platforms like `n8n` or `Zapier`.

---

## **2. MISSION**
Each PR-CYBR agent will implement or verify a function that:
- Enables users to create a TAK Mission Package via a Google Form.
- Syncs data from the form to the `PR-CYBR-MP-DB` (Google Sheets) within seconds.
- Automates the assignment of a unique Order-ID (Order Number) to the mission request.
- Updates the order's current status in the `ORDERS` workspace and triggers alerts to notify both the agent and the user of its progress.
- Packages and delivers a `.zip` file containing mission-specific files (as specified in the Execution section) upon order completion.

---

## **3. EXECUTION**

### **a. Concept of Operations**
1. **Input and Form Creation**
   - Create (if not already present) a Google Form for users to input data fields required for a TAK Mission Package, including but not limited to:
     - Sector-Code
     - Name (Callsign)
     - Email (for delivery)
     - Additional delivery options (if any)

2. **Data Sync to Google Sheets**
   - Configure the form to automatically populate responses in the `PR-CYBR-MP-DB`.
   - Ensure sync occurs within seconds of form submission.

3. **Order-ID Assignment**
   - Use `n8n` or `Zapier` to trigger an automation workflow:
     - Assign a unique Order-ID to the form submission.
     - Populate the Order-ID into the `ORDERS` workspace.

4. **Status Update**
   - Automatically update the status of the order (e.g., "Building Mission Package").
   - Notify the agent (and the user) of the updated status using integrations like email, Slack, or Discord.

5. **Generate and Deliver Mission Package**
   - Create a `.zip` file containing:
     - `ASCOPE.md`
     - `KOCOA.md`
     - `PMESII.md`
     - `POI.md`
     - `OPORD-<ORDER-ID>.md`
     - `PR-<DIV-CODE>-TAK-MP-<MM>-<YEAR>.zip`
   - Store the `.zip` file in a pre-configured storage location or send it to the user via the email address provided.

---

### **b. Tasks**
1. **Agent-Specific Implementation**
   - Verify if the required function exists; otherwise, create and deploy it.
   - Ensure compatibility with all designated tools and platforms (Google Forms, Google Sheets, n8n, Zapier).
   - Ensure logs and audit trails are implemented for all automated actions.

2. **Automation Integration**
   - Configure workflows in `n8n` or `Zapier` to:
     - Assign Order-IDs.
     - Update order statuses dynamically.
     - Trigger appropriate notifications.

3. **Validation and Testing**
   - Perform end-to-end testing of the process.
   - Validate that mission packages are generated and delivered successfully.

---

## **4. SERVICE SUPPORT**

### **a. Tools Required**
- Google Forms and Google Sheets (`PR-CYBR-MP-DB`).
- `n8n` or `Zapier` for automation workflows.
- Storage location for `.zip` delivery.

### **b. API Integration**
- Integrate Google Sheets and Forms APIs to ensure smooth data transfer.
- Utilize `n8n` or `Zapier` API integrations for event-based triggers and actions.

### **c. Dependencies**
- Ensure the `PR-CYBR-MP-DB` structure is correctly configured with:
  - `Order-ID`
  - `Sector-Code`
  - `Name`
  - `Email`
  - `Delivery-Method`
  - `Order-Status`

---

## **5. COMMAND AND SIGNAL**

### **a. Command**
- Each agent must independently execute the above tasks and ensure compliance with the OPORD objectives.
- Coordination with other agents is permitted for shared resources or knowledge.

### **b. Signal**
- Alerts and notifications must be sent to:
  - Users (via email or preferred communication channel).
  - Agent dashboards for tracking and audit purposes.

---

## **6. NOTES AND REFERENCES**
- Reference Google Forms documentation: [https://forms.google.com](https://forms.google.com)
- Reference n8n automation: [https://n8n.io](https://n8n.io)
- Reference Zapier automation: [https://zapier.com](https://zapier.com)
- Example Mission Package `.zip` contents and structure are available in the `PR-CYBR-AGENT` knowledge base.

--- 
End of OPORD-0005.
