## 1. Backend Setup and Startup

1.  **Navigate to the backend directory**:
    ```bash
    cd ./NLTodo/todolist-backend
    ```

2.  **Create and activate a virtual environment**:
    ```bash
    python -m venv .venv
    # macOS / Linux:
    source .venv/bin/activate
    # Windows:
    .venv\Scripts\activate
    ```

3.  **Install dependencies**:
    ```bash
    pip install -r requirements.txt
    ```

4.  **Configure environment variables**:
    In the `.env` file located in the `todolist-backend` directory, you can fill in your DeepSeek API Key:
    ```env
    DEEPSEEK_API_KEY=sk-your-api-key-here
    ```

5.  **Start the server**:
    ```bash
    uvicorn main:app --reload --port 8000
    ```
    The backend service will run at `http://127.0.0.1:8000`.

## 3. Frontend Startup

The frontend is a pure static Single Page Application (SPA) that can be opened directly in a browser.

1.  Locate the `NLTodo/todolist-frontend/index.html` file.
2.  Double-click the file to open it in your browser.

## 4. Usage Instructions

1.  Ensure the backend service is running.
2.  After opening the frontend page, you will see a weekly calendar view.
3.  **Add a task**: Enter a natural language command in the input box at the top, for example:
    *   "Meeting tomorrow at 3 PM"
    *   "Submit report next Friday"
    *   "Go to the gym at 8 PM tonight, high priority"
    Click "Send" or press Enter.
4.  **Delete a task**: Enter commands like "Delete all tasks for today" or "Cancel tomorrow's meeting".
5.  **Manual operations**: Click on a time slot on the calendar to add a task directly; click on an existing task to view details or make modifications.