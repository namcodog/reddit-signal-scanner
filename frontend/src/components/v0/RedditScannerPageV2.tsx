"use client"

import { FormEvent, useState } from "react"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Search, User as UserIcon, LogOut } from "lucide-react"
import NavigationBreadcrumb from "./NavigationBreadcrumb"
import ProductInputFormV2 from "./ProductInputFormV2"
import AnalysisProgressV2 from "./AnalysisProgressV2"
import InsightsReportV2 from "./InsightsReportV2"
import { useAppStateV2, type AppStep } from "@/hooks/useAppStateV2"

export default function RedditScannerPageV2() {
  const { state, actions } = useAppStateV2()

  const [authDialogOpen, setAuthDialogOpen] = useState(false)
  const [authDialogTab, setAuthDialogTab] = useState<"login" | "signup">("login")
  const [authSubmitting, setAuthSubmitting] = useState<"login" | "signup" | null>(null)
  const [loginError, setLoginError] = useState<string | null>(null)
  const [signupError, setSignupError] = useState<string | null>(null)
  const [loginForm, setLoginForm] = useState({ email: "", password: "" })
  const [signupForm, setSignupForm] = useState({ name: "", email: "", password: "" })

  const resetAuthState = () => {
    setAuthSubmitting(null)
    setLoginError(null)
    setSignupError(null)
    setLoginForm({ email: "", password: "" })
    setSignupForm({ name: "", email: "", password: "" })
  }

  const openAuthDialog = (tab: "login" | "signup") => {
    setAuthDialogTab(tab)
    resetAuthState()
    setAuthDialogOpen(true)
  }

  const handleAuthDialogOpenChange = (open: boolean) => {
    setAuthDialogOpen(open)
    if (!open) {
      resetAuthState()
    }
  }

  const handleLoginSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setAuthSubmitting("login")
    setLoginError(null)

    const { email, password } = loginForm
    const result = await actions.login(email.trim(), password)

    if (result.success) {
      handleAuthDialogOpenChange(false)
    } else {
      setLoginError(result.error ?? "登录失败，请稍后重试")
      setAuthSubmitting(null)
    }
  }

  const handleSignupSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setAuthSubmitting("signup")
    setSignupError(null)

    const { name, email, password } = signupForm
    const result = await actions.login(email.trim(), password, name.trim())

    if (result.success) {
      handleAuthDialogOpenChange(false)
    } else {
      setSignupError(result.error ?? "注册失败，请稍后重试")
      setAuthSubmitting(null)
    }
  }

  const isStepEnabled = (stepKey: AppStep) => {
    switch (stepKey) {
      case "input":
        return true
      case "analysis":
        return (
          state.currentStep === "analysis" ||
          Boolean(state.analysis.currentTask) ||
          state.productDescription.trim() !== ""
        )
      case "report":
        return (
          (Boolean(state.analysis.currentTask?.id) && Boolean(state.report.currentReport)) ||
          state.currentStep === "report"
        )
      default:
        return false
    }
  }

  const handleNavigate = (step: AppStep) => {
    if (step === state.currentStep) return
    if (isStepEnabled(step)) {
      actions.setCurrentStep(step)
    }
  }

  const handleStartAnalysis = async (description: string) => {
    const result = await actions.startAnalysis(description)
    if (!result.success && result.error) {
      actions.setError(result.error)
    }
  }

  const handleAnalysisComplete = async (taskId: string) => {
    const result = await actions.loadReport(taskId)
    if (result.success) {
      actions.setCurrentStep("report")
    }
  }

  const handleAnalysisCancel = async () => {
    await actions.cancelAnalysis()
  }

  const handleNewAnalysis = () => {
    actions.setCurrentStep("input")
  }

  const renderCurrentStep = () => {
    switch (state.currentStep) {
      case "input":
        return <ProductInputFormV2 onStartAnalysis={handleStartAnalysis} />
      case "analysis":
        return (
          <AnalysisProgressV2
            productDescription={state.productDescription}
            analysis={state.analysis}
            onComplete={handleAnalysisComplete}
            onCancel={handleAnalysisCancel}
          />
        )
      case "report":
        return (
          <InsightsReportV2
            taskId={state.analysis.currentTask?.id || ""}
            productDescription={state.productDescription}
            onNewAnalysis={handleNewAnalysis}
            reportData={state.report.currentReport}
          />
        )
      default:
        return <ProductInputFormV2 onStartAnalysis={handleStartAnalysis} />
    }
  }

  return (
    <div className="min-h-screen bg-background">
      <header className="border-b border-border bg-card/95 backdrop-blur supports-[backdrop-filter]:bg-card/80">
        <div className="container mx-auto flex items-center justify-between px-4 py-4">
          <div className="flex items-center space-x-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary">
              <Search className="h-5 w-5 text-primary-foreground" />
            </div>
            <div>
              <p className="text-sm font-medium text-muted-foreground">Reddit Business Signals</p>
              <h1 className="text-xl font-semibold text-foreground">Reddit 商业信号扫描器</h1>
            </div>
          </div>
          <div className="flex items-center space-x-4">
            {state.auth.isAuthenticated && state.auth.user ? (
              <>
                <div className="flex items-center space-x-2 rounded-full bg-muted px-3 py-1.5">
                  <UserIcon className="h-4 w-4 text-muted-foreground" />
                  <span className="text-sm text-muted-foreground">欢迎，{state.auth.user.name}</span>
                </div>
                <Button variant="outline" size="sm" onClick={() => { void actions.logout(); }}>
                  <LogOut className="mr-2 h-4 w-4" />退出登录
                </Button>
              </>
            ) : (
              <div className="flex items-center space-x-2">
                <Button variant="outline" size="sm" onClick={() => openAuthDialog("login")}>登录</Button>
                <Button size="sm" onClick={() => openAuthDialog("signup")}>注册</Button>
              </div>
            )}
          </div>
        </div>
      </header>

      <section className="border-b border-border bg-muted/40">
        <div className="container mx-auto px-4 py-6">
          <NavigationBreadcrumb
            currentStep={state.currentStep}
            onNavigate={handleNavigate}
            canNavigateBack
          />
        </div>
      </section>

      {state.error && (
        <div className="container mx-auto px-4 py-4">
          <div className="mx-auto max-w-4xl">
            <div className="rounded-lg border border-destructive/20 bg-destructive/10 p-4">
              <p className="text-sm text-destructive">{state.error}</p>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => actions.clearError()}
                className="mt-2"
              >
                关闭
              </Button>
            </div>
          </div>
        </div>
      )}

      <main className="container mx-auto px-4 py-12">
        <div className="mx-auto max-w-4xl">{renderCurrentStep()}</div>
      </main>

      <Dialog open={authDialogOpen} onOpenChange={handleAuthDialogOpenChange}>
        <DialogContent className="max-w-md p-0">
          <DialogHeader className="space-y-2 px-6 pt-6">
            <DialogTitle className="text-2xl">欢迎使用 Reddit 商业信号扫描器</DialogTitle>
            <DialogDescription>
              登录或创建账户以保存分析历史，并解锁更多商业洞察功能
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-6 px-6 pb-6">
            <Tabs
              value={authDialogTab}
              onValueChange={value => {
                const tab = value as "login" | "signup"
                setAuthDialogTab(tab)
                setAuthSubmitting(null)
                setLoginError(null)
                setSignupError(null)
              }}
              className="space-y-6"
            >
              <TabsList className="grid w-full grid-cols-2">
                <TabsTrigger value="login">登录</TabsTrigger>
                <TabsTrigger value="signup">注册</TabsTrigger>
              </TabsList>

              <TabsContent value="login" className="space-y-4">
                <form className="space-y-4" onSubmit={handleLoginSubmit}>
                  <div className="space-y-2">
                    <Label htmlFor="login-email">邮箱</Label>
                    <Input
                      id="login-email"
                      type="email"
                      required
                      placeholder="you@example.com"
                      value={loginForm.email}
                      onChange={event => setLoginForm(prev => ({ ...prev, email: event.target.value }))}
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="login-password">密码</Label>
                    <Input
                      id="login-password"
                      type="password"
                      required
                      placeholder="请输入密码"
                      value={loginForm.password}
                      onChange={event => setLoginForm(prev => ({ ...prev, password: event.target.value }))}
                    />
                  </div>
                  {loginError && <p className="text-sm text-destructive">{loginError}</p>}
                  <Button type="submit" className="w-full" disabled={authSubmitting === "login"}>
                    {authSubmitting === "login" ? "登录中..." : "登录"}
                  </Button>
                </form>
              </TabsContent>

              <TabsContent value="signup" className="space-y-4">
                <form className="space-y-4" onSubmit={handleSignupSubmit}>
                  <div className="space-y-2">
                    <Label htmlFor="signup-name">姓名</Label>
                    <Input
                      id="signup-name"
                      type="text"
                      required
                      placeholder="请输入姓名"
                      value={signupForm.name}
                      onChange={event => setSignupForm(prev => ({ ...prev, name: event.target.value }))}
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="signup-email">邮箱</Label>
                    <Input
                      id="signup-email"
                      type="email"
                      required
                      placeholder="you@example.com"
                      value={signupForm.email}
                      onChange={event => setSignupForm(prev => ({ ...prev, email: event.target.value }))}
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="signup-password">密码</Label>
                    <Input
                      id="signup-password"
                      type="password"
                      required
                      placeholder="至少 8 位，包含大小写和数字"
                      value={signupForm.password}
                      onChange={event => setSignupForm(prev => ({ ...prev, password: event.target.value }))}
                    />
                  </div>
                  {signupError && <p className="text-sm text-destructive">{signupError}</p>}
                  <Button type="submit" className="w-full" disabled={authSubmitting === "signup"}>
                    {authSubmitting === "signup" ? "创建中..." : "创建账户"}
                  </Button>
                </form>
              </TabsContent>
            </Tabs>
            <p className="text-center text-xs text-muted-foreground">
              登录或注册即表示您同意我们的服务条款与隐私政策
            </p>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  )
}
