import axios from 'axios';

// Create configured Axios instance
const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_URL || '',
  timeout: 10000,
  headers: {
    'Content-Type': 'application/json',
    Accept: 'application/json',
  },
});

/**
 * Checks backend health status.
 * @returns {Promise<{ status: string, application: string }>}
 */
export const checkHealth = async () => {
  try {
    const response = await apiClient.get('/api/health');
    return response.data;
  } catch (error) {
    // If proxied path fails, try direct backend port fallback
    try {
      const fallbackResponse = await axios.get('http://127.0.0.1:8000/api/health', { timeout: 3000 });
      return fallbackResponse.data;
    } catch {
      throw error;
    }
  }
};

/**
 * Sends a natural language chat message to the backend agent.
 * Dispatches to POST /api/chat.
 * @param {string} message
 * @returns {Promise<any>}
 */
export const sendChatMessage = async (message) => {
  try {
    const response = await apiClient.post(
      '/api/chat',
      { message },
      { timeout: 70000 }
    );
    return response.data;
  } catch (error) {
    // If proxied path fails, try direct backend port fallback
    try {
      const fallbackResponse = await axios.post(
        'http://127.0.0.1:8000/api/chat',
        { message },
        {
          headers: { 'Content-Type': 'application/json' },
          timeout: 70000,
        }
      );
      return fallbackResponse.data;
    } catch {
      if (error.response?.data?.message) {
        throw new Error(error.response.data.message);
      }
      throw error;
    }
  }
};

/**
 * Fetches recent task history records from SQLite.
 * @param {number} limit
 * @param {number} offset
 * @returns {Promise<{ tasks: Array<any>, total: number, limit: number, offset: number }>}
 */
export const fetchTasks = async (limit = 50, offset = 0) => {
  try {
    const response = await apiClient.get('/api/tasks', { params: { limit, offset } });
    return response.data;
  } catch (error) {
    try {
      const fallback = await axios.get('http://127.0.0.1:8000/api/tasks', { params: { limit, offset } });
      return fallback.data;
    } catch {
      throw error;
    }
  }
};

/**
 * Fetches complete task details by task ID.
 * @param {string} taskId
 * @returns {Promise<any>}
 */
export const fetchTaskDetail = async (taskId) => {
  try {
    const response = await apiClient.get(`/api/tasks/${taskId}`);
    return response.data;
  } catch (error) {
    try {
      const fallback = await axios.get(`http://127.0.0.1:8000/api/tasks/${taskId}`);
      return fallback.data;
    } catch {
      throw error;
    }
  }
};

/**
 * Deletes a task from persistent storage.
 * @param {string} taskId
 * @returns {Promise<{ success: boolean, message: str, task_id: str }>}
 */
export const deleteTask = async (taskId) => {
  try {
    const response = await apiClient.delete(`/api/tasks/${taskId}`);
    return response.data;
  } catch (error) {
    try {
      const fallback = await axios.delete(`http://127.0.0.1:8000/api/tasks/${taskId}`);
      return fallback.data;
    } catch {
      throw error;
    }
  }
};

/**
 * Downloads validated crawl result JSON for a task.
 * @param {string} taskId
 */
export const downloadTaskResult = async (taskId) => {
  try {
    const response = await apiClient.get(`/api/tasks/${taskId}/result`, {
      responseType: 'blob',
    });
    const blob = new Blob([response.data], { type: 'application/json' });
    const url = window.URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `cli-agent-task-${taskId}.json`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    window.URL.revokeObjectURL(url);
  } catch (error) {
    try {
      const fallback = await axios.get(`http://127.0.0.1:8000/api/tasks/${taskId}/result`, {
        responseType: 'blob',
      });
      const blob = new Blob([fallback.data], { type: 'application/json' });
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `cli-agent-task-${taskId}.json`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(url);
    } catch {
      throw error;
    }
  }
};

/**
 * Previews parsed intent for a natural language task.
 * @param {string} prompt
 * @returns {Promise<any>}
 */
export const previewIntent = async (prompt) => {
  const response = await apiClient.post('/api/intent/preview', { prompt });
  return response.data;
};

/**
 * Requests Groq AI to generate a multi-step task plan (Phase 5).
 * Plan is persisted with status 'pending' awaiting user approval.
 * @param {string} message
 * @returns {Promise<{ success: boolean, plan_id: string, message: string, plan: any }>}
 */
export const generatePlan = async (message) => {
  try {
    const response = await apiClient.post('/api/agent/plan', { message }, { timeout: 30000 });
    return response.data;
  } catch (error) {
    try {
      const fallback = await axios.post('http://127.0.0.1:8000/api/agent/plan', { message }, { timeout: 30000 });
      return fallback.data;
    } catch {
      if (error.response?.data?.message) {
        throw new Error(error.response.data.message);
      }
      throw error;
    }
  }
};

/**
 * Confirms user approval and initiates execution of a multi-step plan.
 * @param {string} planId
 * @param {boolean} approved
 * @returns {Promise<any>}
 */
export const executePlan = async (planId, approved = true) => {
  try {
    const response = await apiClient.post(
      `/api/agent/execute/${planId}`,
      { approved },
      { timeout: 120000 }
    );
    return response.data;
  } catch (error) {
    try {
      const fallback = await axios.post(
        `http://127.0.0.1:8000/api/agent/execute/${planId}`,
        { approved },
        { timeout: 120000 }
      );
      return fallback.data;
    } catch {
      if (error.response?.data?.message) {
        throw new Error(error.response.data.message);
      }
      throw error;
    }
  }
};

/**
 * Cancels a pending plan.
 * @param {string} planId
 * @returns {Promise<any>}
 */
export const cancelPlan = async (planId) => {
  try {
    const response = await apiClient.post(`/api/agent/cancel/${planId}`);
    return response.data;
  } catch (error) {
    try {
      const fallback = await axios.post(`http://127.0.0.1:8000/api/agent/cancel/${planId}`);
      return fallback.data;
    } catch {
      throw error;
    }
  }
};

/**
 * Fetches the current execution status and step traces for a plan.
 * @param {string} planId
 * @returns {Promise<any>}
 */
export const getPlanStatus = async (planId) => {
  try {
    const response = await apiClient.get(`/api/agent/plans/${planId}`);
    return response.data;
  } catch (error) {
    try {
      const fallback = await axios.get(`http://127.0.0.1:8000/api/agent/plans/${planId}`);
      return fallback.data;
    } catch {
      throw error;
    }
  }
};

/**
 * Downloads exported JSON artifact file generated by export_json operation.
 * @param {string} planId
 */
export const downloadPlanExport = async (planId) => {
  try {
    const response = await apiClient.get(`/api/agent/export/${planId}`, {
      responseType: 'blob',
    });
    const blob = new Blob([response.data], { type: 'application/json' });
    const url = window.URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `agent-export-${planId}.json`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    window.URL.revokeObjectURL(url);
  } catch (error) {
    try {
      const fallback = await axios.get(`http://127.0.0.1:8000/api/agent/export/${planId}`, {
        responseType: 'blob',
      });
      const blob = new Blob([fallback.data], { type: 'application/json' });
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `agent-export-${planId}.json`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(url);
    } catch {
      throw error;
    }
  }
};

export default apiClient;

