"use client"
import { Button } from "@/components/ui/button"
import { Search } from "lucide-react"
import ProductInputForm from "@/components/product-input-form"
import AnalysisProgress from "@/components/analysis-progress"
import InsightsReport from "@/components/insights-report"
import NavigationBreadcrumb from "@/components/navigation-breadcrumb"
import AuthDialog from "@/components/auth-dialog"
import { useAppState } from "@/hooks/use-app-state"

export default function HomePage() {
  const [state, actions] = useAppState()

  const handleStartAnalysis = async (description: string) => {
    const result = await actions.startAnalysis(description)
    if (!result.success && result.error) {
      console.error("[v0] Analysis start failed:", result.error)
      actions.setError(result.error)
    }
  }

  const handleAnalysisComplete = async (id: string) => {
    const result = await actions.loadReport(id)
    if (!result.success && result.error) {
      console.error("[v0] Report load failed:", result.error)
      actions.setError(result.error)
    }
  }

  const handleAnalysisCancel = async () => {
    await actions.cancelAnalysis()
  }

  const handleNavigate = (step: "input" | "analysis" | "report") => {
    // Only allow navigation back to completed steps or current step
    const currentStepIndex = ["input", "analysis", "report"].indexOf(state.currentStep)
    const targetStepIndex = ["input", "analysis", "report"].indexOf(step)

    if (targetStepIndex <= currentStepIndex) {
      actions.setCurrentStep(step)
    }
  }

  const handleLogin = async (email: string, password: string) => {
    const result = await actions.login(email, password)
    if (!result.success && result.error) {
      console.error("[v0] Login failed:", result.error)
      actions.setError(result.error)
    }
  }

  const handleSignup = async (name: string, email: string, password: string) => {
    const result = await actions.signup(name, email, password)
    if (!result.success && result.error) {
      console.error("[v0] Signup failed:", result.error)
      actions.setError(result.error)
    }
  }

  return (
    <div className="min-h-screen bg-background">
      <header className="border-b border-border bg-card">
        <div className="container mx-auto px-4 py-4 flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <div className="w-8 h-8 bg-primary rounded-lg flex items-center justify-center">
              <Search className="w-5 h-5 text-primary-foreground" />
            </div>
            <h1 className="text-xl font-bold text-foreground">Reddit 商业信号扫描器</h1>
          </div>
          <div className="flex items-center space-x-4">
            {state.auth.isAuthenticated && state.auth.user ? (
              <>
                <span className="text-sm text-muted-foreground">欢迎，{state.auth.user.name}</span>
                <Button variant="outline" size="sm" onClick={actions.logout}>
                  退出登录
                </Button>
              </>
            ) : (
              <div className="flex items-center space-x-2">
                <AuthDialog onLogin={handleLogin} onSignup={handleSignup}>
                  <Button variant="outline" size="sm">
                    登录
                  </Button>
                </AuthDialog>
                <AuthDialog onLogin={handleLogin} onSignup={handleSignup}>
                  <Button size="sm">注册</Button>
                </AuthDialog>
              </div>
            )}
          </div>
        </div>
      </header>

      <main className="container mx-auto px-4 py-8">
        {state.error && (
          <div className="mb-4 p-4 bg-destructive/10 border border-destructive/20 rounded-lg">
            <p className="text-destructive text-sm">{state.error}</p>
            <Button variant="ghost" size="sm" onClick={() => actions.setError(null)} className="mt-2">
              关闭
            </Button>
          </div>
        )}

        <NavigationBreadcrumb
          currentStep={state.currentStep}
          onNavigate={handleNavigate}
          canNavigateBack={state.currentStep !== "analysis"}
        />

        {state.currentStep === "input" && <ProductInputForm onStartAnalysis={handleStartAnalysis} />}

        {state.currentStep === "analysis" && (
          <AnalysisProgress
            productDescription={state.productDescription}
            onComplete={handleAnalysisComplete}
            onCancel={handleAnalysisCancel}
          />
        )}

        {state.currentStep === "report" && (
          <InsightsReport
            analysisId={state.analysisTask?.id || ""}
            productDescription={state.productDescription}
            onNewAnalysis={actions.resetAnalysis}
          />
        )}
      </main>
    </div>
  )
}
