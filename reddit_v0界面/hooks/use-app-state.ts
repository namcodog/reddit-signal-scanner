"use client"

import { useState, useCallback, useEffect, useRef } from "react"
import type { AppState, AppStep } from "@/types"
import { apiService, ApiError } from "@/services/api"
import { appConfig } from "@/config/app"

interface AppActions {
  // Auth actions
  login: (email: string, password: string) => Promise<{ success: boolean; error?: string }>
  signup: (name: string, email: string, password: string) => Promise<{ success: boolean; error?: string }>
  logout: () => Promise<void>

  // Navigation actions
  setCurrentStep: (step: AppStep) => void

  // Analysis actions
  startAnalysis: (description: string) => Promise<{ success: boolean; taskId?: string; error?: string }>
  cancelAnalysis: () => Promise<void>

  // Report actions
  loadReport: (reportId: string) => Promise<{ success: boolean; error?: string }>
  submitFeedback: (rating: "valuable" | "average" | "not_valuable") => Promise<void>

  // Utility actions
  resetAnalysis: () => void
  setError: (error: string | null) => void
}

const initialState: AppState = {
  currentStep: "input",
  auth: {
    isAuthenticated: false,
    user: null,
    token: null,
  },
  productDescription: "",
  analysisTask: null,
  report: null,
  config: appConfig,
}

export function useAppState(): [AppState & { loading: boolean; error: string | null }, AppActions] {
  const [state, setState] = useState<AppState>(initialState)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const wsRef = useRef<WebSocket | null>(null)
  const pollIntervalRef = useRef<NodeJS.Timeout | null>(null)

  // Initialize auth state from localStorage
  useEffect(() => {
    const initAuth = async () => {
      try {
        const response = await apiService.getCurrentUser()
        if (response.success && response.data) {
          setState((prev) => ({
            ...prev,
            auth: {
              isAuthenticated: true,
              user: response.data!,
              token: localStorage.getItem("auth_token"),
            },
          }))
        }
      } catch (error) {
        // User not authenticated, continue with initial state
        console.log("[v0] User not authenticated")
      }
    }

    initAuth()
  }, [])

  // WebSocket connection for real-time task updates
  const connectWebSocket = useCallback((taskId: string) => {
    if (appConfig.api.useMockData) {
      console.log("[v0] Skipping WebSocket in mock mode, using polling instead")
      startPolling(taskId)
      return
    }

    if (wsRef.current) {
      wsRef.current.close()
    }

    const ws = apiService.createTaskWebSocket(taskId)
    if (!ws) {
      console.log("[v0] WebSocket creation failed, falling back to polling")
      startPolling(taskId)
      return
    }

    ws.onopen = () => {
      console.log("[v0] WebSocket connected for task:", taskId)
    }

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)
        console.log("[v0] WebSocket message:", data)

        if (data.type === "task_update") {
          setState((prev) => ({
            ...prev,
            analysisTask: data.task,
          }))
        }
      } catch (error) {
        console.error("[v0] WebSocket message parse error:", error)
      }
    }

    ws.onerror = (error) => {
      console.error("[v0] WebSocket error:", error)
      if (wsRef.current) {
        wsRef.current.close()
        wsRef.current = null
      }
      // Fallback to polling
      startPolling(taskId)
    }

    ws.onclose = () => {
      console.log("[v0] WebSocket disconnected")
      wsRef.current = null
    }

    wsRef.current = ws
  }, [])

  // Polling fallback for task updates
  const startPolling = useCallback((taskId: string) => {
    if (pollIntervalRef.current) {
      clearInterval(pollIntervalRef.current)
    }

    pollIntervalRef.current = setInterval(async () => {
      try {
        const response = await apiService.getAnalysisTask(taskId)
        if (response.success && response.data) {
          setState((prev) => ({
            ...prev,
            analysisTask: response.data!,
          }))

          // Stop polling if task is completed or failed
          if (response.data.status === "completed" || response.data.status === "failed") {
            if (pollIntervalRef.current) {
              clearInterval(pollIntervalRef.current)
              pollIntervalRef.current = null
            }
          }
        }
      } catch (error) {
        console.error("[v0] Polling error:", error)
      }
    }, 2000) // Poll every 2 seconds
  }, [])

  // Cleanup WebSocket and polling on unmount
  useEffect(() => {
    return () => {
      if (wsRef.current) {
        wsRef.current.close()
      }
      if (pollIntervalRef.current) {
        clearInterval(pollIntervalRef.current)
      }
    }
  }, [])

  const actions: AppActions = {
    login: useCallback(async (email: string, password: string) => {
      setLoading(true)
      setError(null)

      try {
        const response = await apiService.login(email, password)

        if (response.success && response.data) {
          setState((prev) => ({
            ...prev,
            auth: {
              isAuthenticated: true,
              user: response.data!.user,
              token: response.data!.token,
            },
          }))
          return { success: true }
        } else {
          return { success: false, error: response.error || "登录失败" }
        }
      } catch (error) {
        const errorMessage = error instanceof ApiError ? error.message : "网络错误，请重试"
        return { success: false, error: errorMessage }
      } finally {
        setLoading(false)
      }
    }, []),

    signup: useCallback(async (name: string, email: string, password: string) => {
      setLoading(true)
      setError(null)

      try {
        const response = await apiService.signup(name, email, password)

        if (response.success && response.data) {
          setState((prev) => ({
            ...prev,
            auth: {
              isAuthenticated: true,
              user: response.data!.user,
              token: response.data!.token,
            },
          }))
          return { success: true }
        } else {
          return { success: false, error: response.error || "注册失败" }
        }
      } catch (error) {
        const errorMessage = error instanceof ApiError ? error.message : "网络错误，请重试"
        return { success: false, error: errorMessage }
      } finally {
        setLoading(false)
      }
    }, []),

    logout: useCallback(async () => {
      setLoading(true)

      try {
        await apiService.logout()
      } catch (error) {
        console.error("[v0] Logout error:", error)
      } finally {
        setState((prev) => ({
          ...prev,
          auth: {
            isAuthenticated: false,
            user: null,
            token: null,
          },
        }))
        setLoading(false)
      }
    }, []),

    setCurrentStep: useCallback((step: AppStep) => {
      console.log("[v0] Step change:", step)
      setState((prev) => ({ ...prev, currentStep: step }))
    }, []),

    startAnalysis: useCallback(
      async (description: string) => {
        setLoading(true)
        setError(null)

        try {
          setState((prev) => ({ ...prev, productDescription: description }))

          const response = await apiService.createAnalysisTask(description)

          if (response.success && response.data) {
            const task = response.data
            setState((prev) => ({
              ...prev,
              analysisTask: task,
              currentStep: "analysis",
            }))

            // Start real-time updates
            connectWebSocket(task.id)

            return { success: true, taskId: task.id }
          } else {
            return { success: false, error: response.error || "分析启动失败" }
          }
        } catch (error) {
          const errorMessage = error instanceof ApiError ? error.message : "网络错误，请重试"
          return { success: false, error: errorMessage }
        } finally {
          setLoading(false)
        }
      },
      [connectWebSocket],
    ),

    cancelAnalysis: useCallback(async () => {
      const taskId = state.analysisTask?.id
      if (!taskId) return

      setLoading(true)

      try {
        await apiService.cancelAnalysisTask(taskId)

        // Close WebSocket and stop polling
        if (wsRef.current) {
          wsRef.current.close()
        }
        if (pollIntervalRef.current) {
          clearInterval(pollIntervalRef.current)
          pollIntervalRef.current = null
        }

        setState((prev) => ({
          ...prev,
          analysisTask: null,
          currentStep: "input",
        }))
      } catch (error) {
        console.error("[v0] Cancel analysis error:", error)
        setError("取消分析失败")
      } finally {
        setLoading(false)
      }
    }, [state.analysisTask?.id]),

    loadReport: useCallback(async (reportId: string) => {
      setLoading(true)
      setError(null)

      try {
        const response = await apiService.getAnalysisReport(reportId)

        if (response.success && response.data) {
          setState((prev) => ({
            ...prev,
            report: response.data!,
            currentStep: "report",
          }))
          return { success: true }
        } else {
          return { success: false, error: response.error || "报告加载失败" }
        }
      } catch (error) {
        const errorMessage = error instanceof ApiError ? error.message : "网络错误，请重试"
        return { success: false, error: errorMessage }
      } finally {
        setLoading(false)
      }
    }, []),

    submitFeedback: useCallback(
      async (rating: "valuable" | "average" | "not_valuable") => {
        const reportId = state.report?.id
        if (!reportId) return

        try {
          await apiService.submitReportFeedback(reportId, rating)
          console.log("[v0] Feedback submitted:", rating)
        } catch (error) {
          console.error("[v0] Feedback submission error:", error)
        }
      },
      [state.report?.id],
    ),

    resetAnalysis: useCallback(() => {
      console.log("[v0] Analysis reset")

      // Close WebSocket and stop polling
      if (wsRef.current) {
        wsRef.current.close()
      }
      if (pollIntervalRef.current) {
        clearInterval(pollIntervalRef.current)
        pollIntervalRef.current = null
      }

      setState((prev) => ({
        ...prev,
        currentStep: "input",
        productDescription: "",
        analysisTask: null,
        report: null,
      }))
      setError(null)
    }, []),

    setError: useCallback((error: string | null) => {
      setError(error)
    }, []),
  }

  return [{ ...state, loading, error }, actions]
}
