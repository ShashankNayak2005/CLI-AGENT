import React, { useState, useEffect, useCallback } from 'react';
import Sidebar from '../components/Sidebar';
import ChatWindow from '../components/ChatWindow';
import ExecutionPanel from '../components/ExecutionPanel';
import { useBackendHealth } from '../hooks/useBackendHealth';
import {
  sendChatMessage,
  fetchTasks,
  fetchTaskDetail,
  deleteTask,
  generatePlan,
  executePlan,
  cancelPlan,
} from '../services/api';

export const Dashboard = () => {
  const { isOnline, isLoading: backendLoading, healthData, refresh } = useBackendHealth(10000);

  // Task history from SQLite
  const [tasks, setTasks] = useState([]);
  const [activeTaskId, setActiveTaskId] = useState(null);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [historyError, setHistoryError] = useState(null);

  // Active conversation session state
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [isProcessing, setIsProcessing] = useState(false);
  const [agentMode, setAgentMode] = useState(true); // Phase 5 Multi-Step Agent default

  // Execution Telemetry State
  const [telemetry, setTelemetry] = useState({
    taskStatus: 'Idle',
    cliStatus: 'Ready / No process active',
    duration: '0.00s',
    outputPreview: 'No active execution output.',
    errorDisplay: 'None',
    operation: 'None',
    targetUrl: 'None',
    exitCode: 'N/A',
    pagesCrawled: 0,
    pagesFailed: 0,
    outputValidation: 'N/A',
    taskId: 'None',
  });

  // Load task history from SQLite
  const loadHistory = useCallback(async () => {
    setHistoryLoading(true);
    setHistoryError(null);
    try {
      const data = await fetchTasks(50, 0);
      if (data && Array.isArray(data.tasks)) {
        setTasks(data.tasks);
      }
    } catch (err) {
      setHistoryError(err.message || 'Failed to load task history');
    } finally {
      setHistoryLoading(false);
    }
  }, []);

  useEffect(() => {
    loadHistory();
  }, [loadHistory]);

  // Handler for New Chat button
  const handleNewChat = () => {
    setActiveTaskId(null);
    setMessages([]);
    setInput('');
    setTelemetry({
      taskStatus: 'Idle',
      cliStatus: 'Ready / No process active',
      duration: '0.00s',
      outputPreview: 'No active execution output.',
      errorDisplay: 'None',
      operation: 'None',
      targetUrl: 'None',
      exitCode: 'N/A',
      pagesCrawled: 0,
      pagesFailed: 0,
      outputValidation: 'N/A',
      taskId: 'None',
    });
  };

  // Handler for selecting a task from history
  const handleSelectTask = async (taskId) => {
    try {
      setActiveTaskId(taskId);
      const detail = await fetchTaskDetail(taskId);

      // Reconstruct conversation view for this historical task
      const userMsg = {
        id: `hist-user-${detail.id}`,
        sender: 'user',
        text: detail.user_message,
        timestamp: detail.created_at
          ? new Date(detail.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
          : 'Historical',
      };

      const agentMsg = {
        id: `hist-agent-${detail.id}`,
        sender: 'agent',
        text: detail.status === 'completed'
          ? (detail.parsed_result?.website_summary?.description || 'Website crawl completed successfully.')
          : (detail.error_message || `Task finished with status: ${detail.status}`),
        payload: {
          success: detail.status === 'completed',
          task_id: detail.id,
          message: detail.error_message || (detail.status === 'completed' ? 'Website crawl completed successfully.' : `Status: ${detail.status}`),
          intent: {
            intent: detail.intent || 'crawl_website',
            url: detail.target_url,
          },
          execution: {
            status: detail.status,
            exit_code: detail.exit_code,
            duration_seconds: detail.execution_duration,
            stdout: detail.stdout || '',
            stderr: detail.stderr || '',
          },
          result: detail.parsed_result,
        },
        timestamp: detail.completed_at
          ? new Date(detail.completed_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
          : 'Historical',
      };

      setMessages([userMsg, agentMsg]);

      // Update telemetry panel
      const cliCmd = detail.target_url
        ? `python -m app.cli.main crawl --url ${detail.target_url} --output json`
        : 'None';

      setTelemetry({
        taskStatus: detail.status.charAt(0).toUpperCase() + detail.status.slice(1),
        cliStatus: cliCmd,
        duration: `${detail.execution_duration || 0.0}s`,
        outputPreview: detail.stdout || detail.stderr || 'No stdout produced.',
        errorDisplay: detail.status !== 'completed' ? (detail.error_message || detail.status) : 'None',
        operation: detail.intent || 'crawl_website',
        targetUrl: detail.target_url || 'N/A',
        exitCode: detail.exit_code !== null ? detail.exit_code : 'N/A',
        pagesCrawled: detail.parsed_result?.pages_crawled || (detail.status === 'completed' ? 1 : 0),
        pagesFailed: detail.parsed_result?.pages_failed || (detail.status === 'failed' ? 1 : 0),
        outputValidation: detail.result_json ? 'Validated CrawlResult Schema' : 'N/A',
        taskId: detail.id,
      });
    } catch (err) {
      console.error('Failed to load task details:', err);
    }
  };

  // Handler for deleting a task
  const handleDeleteTask = async (taskId) => {
    try {
      await deleteTask(taskId);
      setTasks((prev) => prev.filter((t) => t.id !== taskId));
      if (activeTaskId === taskId) {
        handleNewChat();
      }
    } catch (err) {
      alert(`Failed to delete task: ${err.message}`);
    }
  };

  // Handler for selecting an example prompt
  const handleSelectPrompt = (promptText) => {
    setInput(promptText);
  };

  // Handler for sending messages
  const handleSendMessage = async () => {
    if (!input.trim() || isProcessing) return;

    const userText = input.trim();
    setInput('');

    const userMessage = {
      id: `msg-${Date.now()}`,
      sender: 'user',
      text: userText,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    };

    setMessages((prev) => [...prev, userMessage]);
    setIsProcessing(true);

    const isMultiStep = agentMode || /summarize|summary|export|save|and then|plan|steps/i.test(userText);

    if (isMultiStep) {
      // -------------------------------------------------------------
      // Phase 5: Autonomous Multi-Step Planning (Human-in-the-Loop)
      // -------------------------------------------------------------
      setTelemetry({
        taskStatus: 'Planning',
        cliStatus: 'Groq AI decomposing request into dependency plan...',
        duration: '...',
        outputPreview: `[PLANNER] User instruction: "${userText}"\n[PLANNER] Requesting structured graph decomposition from Groq AI...\n[PLANNER] Validating operations against whitelist (crawl_website, summarize_crawl, export_json)...`,
        errorDisplay: 'None',
      });

      try {
        const planResponse = await generatePlan(userText);

        const agentMessage = {
          id: `msg-${Date.now() + 1}`,
          sender: 'agent',
          text: `Task plan generated with ${planResponse.plan.steps.length} sequential steps. Review the plan below and approve to execute.`,
          plan: planResponse.plan,
          payload: planResponse,
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        };

        setMessages((prev) => [...prev, agentMessage]);

        setTelemetry({
          taskStatus: 'Awaiting Approval',
          cliStatus: `Plan ID: ${planResponse.plan.plan_id} (Awaiting Human Approval)`,
          duration: '0.00s',
          outputPreview: JSON.stringify(planResponse.plan, null, 2),
          errorDisplay: 'None',
          operation: 'multi_step_plan',
          targetUrl: planResponse.plan.steps[0]?.parameters?.url || 'N/A',
          exitCode: 'Pending',
          pagesCrawled: 0,
          pagesFailed: 0,
          outputValidation: 'Validated TaskPlan Schema',
          taskId: planResponse.plan.plan_id,
        });
      } catch (err) {
        const errorMsg = err.message || 'Failed to generate plan.';
        const errorAgentMessage = {
          id: `msg-${Date.now() + 1}`,
          sender: 'agent',
          text: `Error generating plan: ${errorMsg}`,
          payload: { success: false, message: errorMsg },
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        };

        setMessages((prev) => [...prev, errorAgentMessage]);
        setTelemetry({
          taskStatus: 'Rejected',
          cliStatus: 'Plan generation rejected by policy validator',
          duration: '0.00s',
          outputPreview: `[ERROR] ${errorMsg}`,
          errorDisplay: errorMsg,
        });
      } finally {
        setIsProcessing(false);
      }
    } else {
      // -------------------------------------------------------------
      // Phase 3 & 4: Direct CLI Crawl Chat
      // -------------------------------------------------------------
      setTelemetry({
        taskStatus: 'Running',
        cliStatus: 'Groq AI classifying intent & executing CLI subprocess...',
        duration: '...',
        outputPreview: `[PIPELINE] User instruction received: "${userText}"\n[PIPELINE] Calling Groq API with JSON schema enforcement...\n[PIPELINE] Preparing subprocess with shell=False...`,
        errorDisplay: 'None',
      });

      try {
        const chatResponse = await sendChatMessage(userText);

        const agentMessage = {
          id: `msg-${Date.now() + 1}`,
          sender: 'agent',
          text: chatResponse.message,
          payload: chatResponse,
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        };

        setMessages((prev) => [...prev, agentMessage]);

        if (chatResponse.task_id) {
          setActiveTaskId(chatResponse.task_id);
        }

        const execution = chatResponse.execution || {};
        const statusLabel =
          execution.status === 'completed'
            ? 'Completed'
            : execution.status === 'rejected'
            ? 'Rejected'
            : 'Failed';

        const cliCmd =
          chatResponse.intent?.intent === 'crawl_website'
            ? `python -m app.cli.main crawl --url ${chatResponse.intent.url} --max-pages ${chatResponse.intent.max_pages || 5} --max-depth ${chatResponse.intent.max_depth || 1} --output json`
            : 'None (Intent rejected or unsupported)';

        setTelemetry({
          taskStatus: statusLabel,
          cliStatus: cliCmd,
          duration: `${execution.duration_seconds || 0.0}s`,
          outputPreview: execution.stdout || execution.stderr || chatResponse.message || 'No process output.',
          errorDisplay: !chatResponse.success ? chatResponse.message : 'None',
          operation: chatResponse.intent?.intent || 'crawl_website',
          targetUrl: chatResponse.intent?.url || 'N/A',
          exitCode: execution.exit_code !== undefined && execution.exit_code !== null ? execution.exit_code : 'N/A',
          pagesCrawled: chatResponse.result?.pages_crawled || (execution.status === 'completed' ? 1 : 0),
          pagesFailed: chatResponse.result?.pages_failed || (execution.status === 'failed' ? 1 : 0),
          outputValidation: chatResponse.result ? 'Validated CrawlResult JSON' : 'None',
          taskId: chatResponse.task_id || 'N/A',
        });

        loadHistory();
      } catch (err) {
        const errorMsg = err.message || 'Failed to communicate with backend service.';
        const errorAgentMessage = {
          id: `msg-${Date.now() + 1}`,
          sender: 'agent',
          text: `Error processing request: ${errorMsg}`,
          payload: {
            success: false,
            message: errorMsg,
            intent: { intent: 'unsupported' },
            execution: {
              status: 'failed',
              exit_code: -1,
              duration_seconds: 0.0,
              stdout: '',
              stderr: errorMsg,
            },
          },
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        };

        setMessages((prev) => [...prev, errorAgentMessage]);
        setTelemetry({
          taskStatus: 'Failed',
          cliStatus: 'Execution halted on error',
          duration: '0.00s',
          outputPreview: `[ERROR] ${errorMsg}`,
          errorDisplay: errorMsg,
        });

        loadHistory();
      } finally {
        setIsProcessing(false);
      }
    }
  };

  // Phase 5: Plan Approval Handler
  const handleApprovePlan = async (planId) => {
    setIsProcessing(true);
    setTelemetry({
      taskStatus: 'Running',
      cliStatus: `Executing Plan: ${planId} (Controlled operation registry)`,
      duration: '...',
      outputPreview: `[AGENT] Approval confirmed by user. Dispatching approved operations for ${planId}...`,
      errorDisplay: 'None',
    });

    try {
      const execRes = await executePlan(planId, true);

      setMessages((prev) =>
        prev.map((msg) => {
          const curPlan = msg.plan || msg.payload?.plan;
          if (curPlan?.plan_id === planId) {
            const updatedPlan = {
              ...curPlan,
              status: execRes.status,
              total_duration: execRes.total_duration,
              steps: execRes.steps || curPlan.steps,
              final_result: execRes.final_result,
              error_message: execRes.status === 'failed' ? execRes.message : null,
            };
            return {
              ...msg,
              plan: updatedPlan,
              payload: { ...(msg.payload || {}), plan: updatedPlan },
            };
          }
          return msg;
        })
      );

      const crawlStep = execRes.steps?.find((s) => s.operation === 'crawl_website');
      const crawlUrl = crawlStep?.output?.target_url || 'https://example.com';
      const pagesCrawled = execRes.final_result?.crawl?.pages_crawled || (execRes.status === 'completed' ? 1 : 0);
      const pagesFailed = execRes.final_result?.crawl?.pages_failed || (execRes.status === 'failed' ? 1 : 0);

      setTelemetry({
        taskStatus: execRes.status === 'completed' ? 'Completed' : 'Failed',
        cliStatus: `Plan ${planId} execution concluded`,
        duration: `${execRes.total_duration || 0.0}s`,
        outputPreview: JSON.stringify(execRes.final_result || execRes.steps, null, 2),
        errorDisplay: execRes.status === 'failed' ? execRes.message : 'None',
        operation: 'multi_step_agent',
        targetUrl: crawlUrl,
        exitCode: execRes.status === 'completed' ? 0 : 'Non-Zero',
        pagesCrawled: pagesCrawled,
        pagesFailed: pagesFailed,
        outputValidation: 'Validated Multi-Step Output & Summary',
        taskId: planId,
      });

      loadHistory();
    } catch (err) {
      const errMsg = err.message || 'Execution error';
      setTelemetry({
        taskStatus: 'Failed',
        cliStatus: `Plan ${planId} failed`,
        duration: '0.00s',
        outputPreview: `[ERROR] ${errMsg}`,
        errorDisplay: errMsg,
      });
    } finally {
      setIsProcessing(false);
    }
  };

  // Phase 5: Plan Cancellation Handler
  const handleCancelPlan = async (planId) => {
    try {
      await cancelPlan(planId);
      setMessages((prev) =>
        prev.map((msg) => {
          const curPlan = msg.plan || msg.payload?.plan;
          if (curPlan?.plan_id === planId) {
            const updatedPlan = {
              ...curPlan,
              status: 'cancelled',
            };
            return {
              ...msg,
              plan: updatedPlan,
              payload: { ...(msg.payload || {}), plan: updatedPlan },
            };
          }
          return msg;
        })
      );

      setTelemetry((prev) => ({
        ...prev,
        taskStatus: 'Cancelled',
        cliStatus: `Plan ${planId} cancelled by user.`,
        errorDisplay: 'None',
      }));
    } catch (err) {
      alert(`Failed to cancel plan: ${err.message}`);
    }
  };

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-[#080c14] text-slate-100 font-sans">
      {/* Left Sidebar with Task History */}
      <Sidebar
        tasks={tasks}
        activeTaskId={activeTaskId}
        onSelectTask={handleSelectTask}
        onNewChat={handleNewChat}
        onDeleteTask={handleDeleteTask}
        onRefreshHistory={loadHistory}
        historyLoading={historyLoading}
        historyError={historyError}
        isBackendOnline={isOnline}
        backendLoading={backendLoading}
        onRefreshBackend={refresh}
      />

      {/* Main Chat Area */}
      <ChatWindow
        messages={messages}
        input={input}
        setInput={setInput}
        onSendMessage={handleSendMessage}
        onSelectPrompt={handleSelectPrompt}
        onApprovePlan={handleApprovePlan}
        onCancelPlan={handleCancelPlan}
        isLoading={isProcessing}
        agentMode={agentMode}
        setAgentMode={setAgentMode}
      />

      {/* Right Execution Telemetry Panel */}
      <ExecutionPanel
        taskStatus={telemetry.taskStatus}
        cliStatus={telemetry.cliStatus}
        duration={telemetry.duration}
        outputPreview={telemetry.outputPreview}
        errorDisplay={telemetry.errorDisplay}
        operation={telemetry.operation}
        targetUrl={telemetry.targetUrl}
        exitCode={telemetry.exitCode}
        pagesCrawled={telemetry.pagesCrawled}
        pagesFailed={telemetry.pagesFailed}
        outputValidation={telemetry.outputValidation}
        taskId={telemetry.taskId}
      />
    </div>
  );
};

export default Dashboard;
