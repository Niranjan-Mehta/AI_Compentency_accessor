import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import { api, clearTokens, hasSession, toFormData } from '../services/api.js';

const AppContext = createContext(null);

function profileView(profile) {
  const fullName = [profile.first_name, profile.last_name].filter(Boolean).join(' ') || profile.username;
  return {
    ...profile,
    fullName,
    name: profile.first_name || fullName.split(' ')[0],
    roleLabel: profile.role === 'TA' ? 'Teaching Assistant' : profile.role === 'FACULTY' ? 'Faculty' : 'Trainee',
    level: profile.level || '—',
    levelName: profile.level ? `Competency ${profile.level}` : 'Not yet rated',
    nextLevel: profile.level === 'L4' ? 'Highest level' : 'Keep building skills',
    completedSegments: Number(String(profile.level || '').slice(1)) || 0,
    totalSegments: 4,
    avatar: fullName.split(/\s+/).map((part) => part[0]).join('').slice(0, 2).toUpperCase(),
  };
}

function taskView(task, submission, questionState, evaluationState, report) {
  const dueDate = task.due_date ? new Date(task.due_date) : null;
  const dueInDays = dueDate ? (dueDate.getTime() - Date.now()) / 86400000 : Infinity;
  let status = 'not-submitted';
  let statusLabel = 'Not submitted';
  let actionType = 'submit';
  let actionLabel = 'Submit';
  if (submission) {
    if (submission.status === 'SUBMITTED' || submission.status === 'PROCESSING') {
      status = 'processing'; statusLabel = submission.status === 'SUBMITTED' ? 'Starting processing' : 'Processing';
      actionType = 'processing-time'; actionLabel = statusLabel;
    } else if (submission.status === 'FAILED') {
      status = 'processing'; statusLabel = 'Processing failed'; actionType = 'retry-processing'; actionLabel = 'Retry processing';
    } else if (submission.status === 'QUESTIONS_READY') {
      if (!questionState || questionState.status === 'NOT_STARTED' || questionState.status === 'FAILED') {
        status = 'questions-ready'; statusLabel = 'Questions ready'; actionType = 'questions'; actionLabel = 'Generate questions';
      } else if (questionState.status === 'PROCESSING') {
        status = 'processing'; statusLabel = 'Generating questions'; actionType = 'processing-time'; actionLabel = statusLabel;
      } else if (evaluationState?.status === 'EVALUATING' || evaluationState?.status === 'SUBMITTED') {
        status = 'under-review'; statusLabel = 'Evaluating answers'; actionType = 'view-submission'; actionLabel = statusLabel;
      } else if (evaluationState?.status === 'EVALUATED' || evaluationState?.status === 'FAILED') {
        status = 'under-review'; statusLabel = evaluationState.status === 'FAILED' ? 'Evaluation failed' : 'TA review';
        actionType = evaluationState.status === 'FAILED' ? 'retry-evaluation' : 'view-submission'; actionLabel = evaluationState.status === 'FAILED' ? 'Retry evaluation' : 'View feedback';
      } else {
        status = 'questions-ready'; statusLabel = 'Questions ready'; actionType = 'questions'; actionLabel = 'Answer questions';
      }
    } else if (submission.status === 'ANSWERS_SUBMITTED' || submission.status === 'UNDER_REVIEW') {
      status = 'under-review'; statusLabel = 'Under review'; actionType = 'view-submission'; actionLabel = 'View status';
    }
    if (report) {
      status = 'published'; statusLabel = 'Report published'; actionType = 'view-report'; actionLabel = 'View report';
    }
  }
  const dueText = dueDate ? `${dueDate.toLocaleDateString(undefined, { day: 'numeric', month: 'short' })}${dueInDays < 0 ? ' (past due)' : ''}` : 'No due date';
  return {
    ...task,
    name: task.title,
    dueText: task.due_date ? `Due ${dueText}` : dueText,
    dueBadge: dueInDays >= 0 && dueInDays <= 1.5,
    status,
    statusLabel,
    actionType,
    actionLabel,
    submission,
    reportId: report?.id,
    assessmentRunId: questionState?.assessment_run_id,
  };
}

export const AppProvider = ({ children }) => {
  const [currentUser, setCurrentUser] = useState(null);
  const [tasks, setTasks] = useState([]);
  const [batches, setBatches] = useState([]);
  const [rubrics, setRubrics] = useState([]);
  const [submissions, setSubmissions] = useState([]);
  const [assessments, setAssessments] = useState([]);
  const [reports, setReports] = useState({});
  const [questionsByTask, setQuestionsByTask] = useState({});
  const [activeTaskId, setActiveTaskId] = useState(null);
  const [activeReportId, setActiveReportId] = useState(null);
  const [activeAssessmentRunId, setActiveAssessmentRunId] = useState(null);
  const [submissionModalTask, setSubmissionModalTask] = useState(null);
  const [loading, setLoading] = useState(false);
  const [appError, setAppError] = useState('');
  const [notice, setNotice] = useState('');
  const [authReady, setAuthReady] = useState(false);

  const publishedReportsList = useMemo(
    () => Object.values(reports).filter((report) => report.status === 'PUBLISHED'),
    [reports],
  );
  const averageScore = useMemo(() => {
    if (!publishedReportsList.length) return 0;
    return Math.round(publishedReportsList.reduce((total, report) => total + Number(report.overall_score || 0), 0) / publishedReportsList.length);
  }, [publishedReportsList]);
  const todoTasks = useMemo(() => tasks.filter((task) => ['not-submitted', 'questions-ready'].includes(task.status)), [tasks]);
  const doneTasks = useMemo(() => tasks.filter((task) => ['processing', 'under-review', 'published'].includes(task.status)), [tasks]);
  const dueTomorrowCount = useMemo(() => tasks.filter((task) => task.dueBadge && task.status === 'not-submitted').length, [tasks]);

  const refreshWorkspace = useCallback(async (roleOverride) => {
    const role = roleOverride || currentUser?.role;
    if (!role) return;
    setLoading(true);
    setAppError('');
    try {
      const [batchRows, taskRows, submissionRows, reportRows, assessmentRows, rubricRows] = await Promise.all([
        api.all('/batches/'),
        role === 'TRAINEE' ? api.all('/tasks/assigned-to-trainee/')
          : role === 'TA' ? api.all('/tasks/assigned-to-ta/') : api.all('/tasks/'),
        api.all('/submissions/'),
        api.all('/reports/'),
        api.all('/assessment-runs/'),
        role === 'FACULTY' ? api.all('/rubrics/') : Promise.resolve([]),
      ]);

      const reportsMap = Object.fromEntries(reportRows.map((report) => [report.id, {
        ...report,
        taskName: report.task_title || report.snapshot?.task?.title || 'Assessment report',
        overallScore: Number(report.overall_score || 0),
        level: report.competency_level || report.snapshot?.competency_level || '—',
        reviewedBy: report.published_by ? 'Faculty' : 'Teaching Assistant',
        criteria: (report.snapshot?.criteria || []).map((criterion) => ({
          id: criterion.criterion_id, name: criterion.name,
          score: Number(criterion.score || 0), maxScore: criterion.max_score,
          level: criterion.level, feedback: criterion.feedback || [],
        })),
      }]));
      let decoratedTasks = taskRows.map((task) => {
        const submission = submissionRows.find((item) => item.task?.id === task.id && item.is_active !== false);
        const report = reportRows.find((item) => item.task_id === task.id && item.status === 'PUBLISHED');
        return taskView(task, submission, null, null, report);
      });

      if (role === 'TRAINEE') {
        decoratedTasks = await Promise.all(decoratedTasks.map(async (task) => {
          if (!task.submission || task.submission.status !== 'QUESTIONS_READY') return task;
          try {
            const questionState = await api.request(`/submissions/${task.submission.id}/questions/`);
            let evaluationState = null;
            if (questionState.assessment_run_id) {
              evaluationState = await api.request(`/assessment-runs/${questionState.assessment_run_id}/evaluation-status/`);
            }
            return taskView(task, task.submission, questionState, evaluationState, task.reportId ? reportsMap[task.reportId] : null);
          } catch {
            return task;
          }
        }));
      }

      setBatches(batchRows);
      setTasks(decoratedTasks);
      setSubmissions(submissionRows);
      setReports(reportsMap);
      setAssessments(assessmentRows);
      setRubrics(rubricRows);
      const latestPublished = reportRows.find((report) => report.status === 'PUBLISHED');
      if (latestPublished) {
        const level = latestPublished.snapshot?.competency_level || latestPublished.competency_level;
        setCurrentUser((user) => user ? { ...user, level, levelName: level ? `Competency ${level}` : 'Not yet rated', nextLevel: level === 'L4' ? 'Highest level' : 'Continue building skills', completedSegments: Number(String(level || 'L0').slice(1)) || 0, totalSegments: 4 } : user);
      }
      if (decoratedTasks.length && !decoratedTasks.some((task) => task.id === activeTaskId)) setActiveTaskId(decoratedTasks[0].id);
      if (reportRows.length && !reportRows.some((report) => report.id === activeReportId)) setActiveReportId(reportRows[0].id);
    } catch (error) {
      setAppError(error.message);
    } finally {
      setLoading(false);
    }
  }, [currentUser?.role, activeTaskId, activeReportId]);

  const login = useCallback(async (identifier, password, remember) => {
    setLoading(true);
    setAppError('');
    try {
      const { profile } = await api.login(identifier, password, remember);
      const user = profileView(profile);
      setCurrentUser(user);
      await refreshWorkspace(user.role);
      return user;
    } finally {
      setLoading(false);
      setAuthReady(true);
    }
  }, [refreshWorkspace]);

  const logout = useCallback(async () => {
    try { await api.logout(); } catch { clearTokens(); }
    setCurrentUser(null);
    setTasks([]); setBatches([]); setRubrics([]); setSubmissions([]);
    setAssessments([]); setReports({}); setQuestionsByTask({});
    setActiveTaskId(null); setActiveReportId(null); setActiveAssessmentRunId(null); setAppError(''); setNotice('');
  }, []);

  useEffect(() => {
    const expired = () => {
      setCurrentUser(null);
      setAppError('Your session expired. Please sign in again.');
    };
    window.addEventListener('assessor:session-expired', expired);
    if (hasSession()) {
      api.profile().then((profile) => {
        const user = profileView(profile);
        setCurrentUser(user);
        return refreshWorkspace(user.role);
      }).catch(() => clearTokens()).finally(() => setAuthReady(true));
    } else {
      setAuthReady(true);
    }
    return () => window.removeEventListener('assessor:session-expired', expired);
  }, []);

  useEffect(() => {
    if (currentUser?.role !== 'TRAINEE' || !tasks.some((task) => ['processing', 'under-review'].includes(task.status))) return undefined;
    const timer = window.setInterval(() => refreshWorkspace(), 5000);
    return () => window.clearInterval(timer);
  }, [currentUser?.role, tasks, refreshWorkspace]);

  const submitWork = async (taskId, { repoUrl, branch, file }) => {
    const form = toFormData({ task: taskId, repository_url: repoUrl, branch, project_pdf: file });
    const submission = await api.request('/submissions/', { method: 'POST', body: form });
    await api.request(`/submissions/${submission.id}/process/`, { method: 'POST' });
    setNotice('Your work was submitted. Repository and PDF processing has started.');
    await refreshWorkspace();
    return submission;
  };

  const startProcessing = async (taskId) => {
    const task = tasks.find((item) => item.id === Number(taskId) || item.id === taskId);
    if (!task?.submission) throw new Error('No submission was found for this task.');
    const result = await api.request(`/submissions/${task.submission.id}/process/`, { method: 'POST' });
    await refreshWorkspace();
    return result;
  };

  const startQuestionGeneration = async (taskId) => {
    const task = tasks.find((item) => item.id === Number(taskId) || item.id === taskId);
    if (!task?.submission) throw new Error('No submission was found for this task.');
    const result = await api.request(`/submissions/${task.submission.id}/generate-questions/`, { method: 'POST' });
    setNotice('Question generation has started. This screen will update when it is complete.');
    await refreshWorkspace();
    return result;
  };

  const loadQuestionsForTask = async (taskId) => {
    const task = tasks.find((item) => item.id === Number(taskId) || item.id === taskId);
    if (!task?.submission) throw new Error('No submission was found for this task.');
    const questionState = await api.request(`/submissions/${task.submission.id}/questions/`);
    if (questionState.status !== 'COMPLETED' || !questionState.assessment_run_id) {
      if (questionState.status === 'PROCESSING') throw new Error('Questions are still being generated.');
      throw new Error('Questions are not ready for this submission.');
    }
    const answerState = await api.request(`/assessment-runs/${questionState.assessment_run_id}/answers/`);
    const questions = questionState.results.map((question) => {
      const saved = answerState.questions.find((item) => item.question.id === question.id)?.answer;
      const snippetLines = (question.code_snippet || '').split('\n').filter(Boolean);
      return {
        ...question,
        title: `Question ${question.display_order}`,
        prompt: question.question_text,
        tags: [question.competency_criterion?.name, question.difficulty].filter(Boolean),
        codeFile: question.code_file || 'Project context',
        codeLine: question.code_line || null,
        codeLines: snippetLines.map((text, index) => ({ num: (question.code_line || 1) + index, text, highlighted: index === 0 })),
        answer: saved?.answer_text || '',
        isSaved: Boolean(saved),
        savedTime: saved?.updated_at ? new Date(saved.updated_at).toLocaleTimeString() : '',
      };
    });
    setQuestionsByTask((previous) => ({
      ...previous,
      [taskId]: { assessmentRunId: questionState.assessment_run_id, status: answerState.status, questions },
    }));
    setActiveTaskId(taskId);
    setActiveAssessmentRunId(questionState.assessment_run_id);
    return questions;
  };

  const getQuestionsForTask = (taskId) => questionsByTask[taskId]?.questions || [];
  const updateQuestion = (taskId, questionId, updates) => {
    setQuestionsByTask((previous) => ({
      ...previous,
      [taskId]: {
        ...previous[taskId],
        questions: (previous[taskId]?.questions || []).map((question) => question.id === questionId ? { ...question, ...updates } : question),
      },
    }));
  };
  const saveQuestionDraft = async (taskId, questionId, answer) => {
    const state = questionsByTask[taskId];
    if (!state?.assessmentRunId) throw new Error('Load the assessment questions before saving an answer.');
    if (!answer.trim()) throw new Error('Enter an answer before saving this draft.');
    await api.request(`/assessment-runs/${state.assessmentRunId}/answers/`, jsonPost({ question_id: questionId, answer_text: answer }));
    updateQuestion(taskId, questionId, { answer, isSaved: true, savedTime: new Date().toLocaleTimeString() });
    setNotice('Draft answer saved.');
  };
  const submitAllQuestions = async (taskId) => {
    const state = questionsByTask[taskId];
    if (!state?.assessmentRunId) throw new Error('Assessment questions are not loaded.');
    const result = await api.request(`/assessment-runs/${state.assessmentRunId}/submit-answers/`, { method: 'POST' });
    setNotice('Answers submitted. Evaluation is running in the background.');
    await refreshWorkspace();
    return result;
  };

  const getReport = (reportId) => reports[reportId] || Object.values(reports).find((report) => report.status === 'PUBLISHED') || null;
  const todoCount = todoTasks.length;
  const doneCount = doneTasks.length;
  const value = {
    currentUser, setCurrentUser, tasks, setTasks, batches, setBatches, rubrics, setRubrics,
    submissions, setSubmissions, assessments, reports, setReports, questionsByTask,
    todoTasks, doneTasks, todoCount, doneCount, dueTomorrowCount,
    publishedReportsList, publishedCount: publishedReportsList.length, averageScore,
    activeTaskId, setActiveTaskId, activeReportId, setActiveReportId, activeAssessmentRunId, setActiveAssessmentRunId,
    submissionModalTask, setSubmissionModalTask, loading, authReady, appError, setAppError, notice, setNotice,
    login, logout, refreshWorkspace, submitWork, startProcessing, startQuestionGeneration,
    loadQuestionsForTask, getQuestionsForTask, updateQuestion, saveQuestionDraft,
    submitAllQuestions, getReport, api,
  };
  return <AppContext.Provider value={value}>{children}</AppContext.Provider>;
};

function jsonPost(body) {
  return { method: 'POST', body: JSON.stringify(body) };
}

export const useApp = () => {
  const context = useContext(AppContext);
  if (!context) throw new Error('useApp must be used within an AppProvider');
  return context;
};
