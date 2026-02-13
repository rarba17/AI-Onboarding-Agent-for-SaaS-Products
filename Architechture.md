Probable Error-Free Architectural Design
----------------------------------------

This architecture is designed for scalability, resilience, and clear separation of concerns, using the specified tech stack.

![image-20260214022514907](/home/abrar/.config/Typora/typora-user-images/image-20260214022514907.png)

### Component Breakdown

#### 1\. Client-Side Integration (SaaS Product)

*   **JS SDK:** A small library (**onboarding-agent-sdk.js**).
    
    *   **Functionality:**
        
        *   Initializes with an API key.
            
        *   Automatically captures DOM events (**click**, **change**, **submit**) and **page\_view** events.
            
        *   Debounces rapid-fire events (e.g., typing) to prevent API spam.
            
        *   Batches events and sends them to the FastAPI **/events** endpoint every 5 seconds or when the batch reaches 10 events.
            
        *   Establishes a persistent WebSocket connection to the **/ws/{user\_id}** endpoint on load.
            
        *   Listens for messages on the WebSocket and renders them as tooltips or chat messages using a lightweight, injectable CSS/JS framework.
    
*   **Error Handling:**
    
    *   If the API is unreachable, events are stored in **localStorage** and sent when connection is restored.
        
    *   If the WebSocket connection drops, the SDK automatically attempts to reconnect with exponential backoff.
        
    *   All SDK code is wrapped in a **try...catch** block to ensure it never breaks the host application.
        

#### 2\. API Gateway & Backend (FastAPI)

*   **Framework:** FastAPI, chosen for its high performance (async/await) and automatic OpenAPI documentation.
    
*   **Key Endpoints:**
    
    *   **POST /api/v1/events**: Receives the batched event JSON. It validates the data with Pydantic models and immediately pushes it to a Redis Stream. It returns a **202 Accepted** response instantly. This makes the endpoint extremely fast and non-blocking.
        
    *   **WebSocket /ws/{user\_id}**: Authenticates the user (via a token passed in the query string) and manages the WebSocket connection for sending real-time nudges.
        
    *   **GET/POST /api/v1/config**: Endpoints used by the React Dashboard to fetch and update configuration (tone, baselines, etc.).
    
*   **Error Handling:**
    
    *   Uses Pydantic for robust request validation, returning **422 Unprocessable Entity** for malformed data.
        
    *   A global exception handler catches unexpected errors, logs them, and returns a generic **500 Internal Server Error** to avoid leaking implementation details.
        
    *   API requests are authenticated via a secure **X-API-Key** header.
        

#### 3\. Data Layer

*   **PostgreSQL (The Source of Truth):**
    
    *   **Schema:**
        
        *   **users** (**user\_id**, **company\_id**, **signup\_date**, **metadata**)
            
        *   **events** (**event\_id**, **user\_id**, **session\_id**, **event\_type**, **target\_element**, **timestamp**, **properties\_jsonb**)
            
        *   **sessions** (**session\_id**, **user\_id**, **start\_time**, **last\_seen\_time**, **is\_active**)
            
        *   **nudges** (**nudge\_id**, **user\_id**, **session\_id**, **stuck\_point**, **nudge\_type**, **content**, **sent\_at**, **status**)
            
        *   **baselines** (**baseline\_id**, **company\_id**, **event\_sequence\_jsonb**)
        
    *   **Why:** Reliability, ACID transactions for data consistency, and powerful querying with JSONB for unstructured event properties.
    
*   **Redis (The High-Speed Layer):**
    
    *   **Use Cases:**
        
        1.  **Message Queue:** A Redis Stream (**events\_stream**) acts as a durable, high-throughput queue between the FastAPI endpoint and the LangGraph workers.
            
        2.  **Session State Cache:** A hash (**session:{user\_id}**) stores the current session's state, last seen event, and a counter for nudges per stuck point. This allows for instant lookups by the Diagnosis Agent.
            
        3.  **Real-time Connection Mapping:** A Redis Set (**ws\_connections**) maps **user\_id** to the specific WebSocket server instance handling their connection (important for horizontal scaling).
        
    *   **Why:** Sub-millisecond latency, which is critical for real-time features and session management.
        

#### 4\. AI Core (LangGraph)

LangGraph is the perfect orchestrator for our multi-agent workflow. It allows us to define the state and the flow of logic between agents declaratively.

*   **Workflow Trigger:** A separate worker process (e.g., a Celery worker or a simple Python script) consumes messages from the **events\_stream** in Redis. When a new event arrives, it either updates the session state in Redis or, if the event meets a trigger condition (inactivity, "stuck" event), it invokes the LangGraph workflow.
    
*   **LangGraph Workflow Definition:**
    
    1.  **State:** The initial state passed to the graph is the **user\_id** and **session\_id**.
        
    2.  **Node 1: Diagnosis Agent:**
        
        *   Fetches the user's full session history from PostgreSQL and the current state from Redis.
            
        *   Fetches the company's "Success Baseline" from PostgreSQL.
            
        *   Constructs a detailed prompt for an LLM (e.g., GPT-4o).
            
        *   **Prompt Engineering:** The prompt is critical. It instructs the LLM to act as a user experience analyst, providing the user's event stream, the baseline, and asking for a structured JSON diagnosis. It includes few-shot examples to guide the LLM's output format.
            
        *   Uses structured output (e.g., **response\_format={"type": "json\_object"}**) to ensure the LLM returns valid JSON that matches our Pydantic **Diagnosis** model.
        
    3.  **Node 2: Decision Router:** A simple conditional edge in LangGraph that checks the **confidence\_score** from the diagnosis. If it's below a threshold (e.g., 0.6), the workflow ends to avoid sending unhelpful nudges.
        
    4.  **Node 3: Coach Agent:**
        
        *   Receives the diagnosis.
            
        *   Fetches the company's "Tone and Voice" settings.
            
        *   Constructs a prompt for the LLM to generate the nudge content, specifying the desired tone and format.
            
        *   Again, uses structured output to get a valid **Nudge** object.
        
    5.  **Node 4: Action Taker:**
        
        *   This node executes the plan.
            
        *   It increments the nudge counter in Redis.
            
        *   It saves the nudge to PostgreSQL for logging.
            
        *   It sends the nudge payload to the correct WebSocket server instance (using the Redis connection map) for real-time delivery.
            
        *   If the counter is now > **N**, it triggers the Escalation Agent.
        
    6.  **Node 5: Escalation Agent (Conditional):**
        
        *   Receives the full context (user history, diagnosis, past nudges).
            
        *   Prompts the LLM to draft a concise, human-readable alert.
            
        *   Sends the alert via a webhook (e.g., to Slack) or email.
    
*   **Error Handling & Resilience:**
    
    *   **LLM API Failures:** The LangGraph nodes that call the LLM will be wrapped in a retry mechanism with exponential backoff. If the LLM API is down after several retries, the workflow fails gracefully, logs the error, and no nudge is sent.
        
    *   **LLM Hallucinations:** Using structured output and Pydantic validation drastically reduces the risk of malformed data from the LLM. If validation fails, the workflow terminates and logs the error.
        
    *   **Agent Failures:** If any agent node fails, LangGraph's state management allows for inspection and retrying the workflow from the point of failure.
        

#### 5\. Admin Dashboard (React)

*   A standard Single Page Application (SPA) built with React.
    
*   It communicates exclusively with the FastAPI backend's **/api/v1/config** and other data-fetching endpoints.
    
*   It uses a charting library (like Chart.js or Recharts) to visualize the onboarding funnel.
    
*   Authentication is handled via a standard login flow (e.g., OAuth2 with JWT), issuing a short-lived token for API calls.
    

This architecture provides a robust, scalable, and maintainable foundation for the AI Onboarding Agent, directly addressing the core requirements while anticipating and mitigating potential errors