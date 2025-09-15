"use client"

import { useState } from "react"
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { ThumbsUp, Meh, ThumbsDown, Star } from "lucide-react"

interface ReportEvaluationDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  onEvaluationComplete: () => void
}

export default function ReportEvaluationDialog({
  open,
  onOpenChange,
  onEvaluationComplete,
}: ReportEvaluationDialogProps) {
  const [selectedRating, setSelectedRating] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)

  const evaluationOptions = [
    {
      value: "valuable",
      label: "有价值",
      description: "这份报告对我很有帮助",
      icon: ThumbsUp,
      color: "text-green-600",
      bgColor: "bg-green-50 hover:bg-green-100 border-green-200",
      selectedBg: "bg-green-100 border-green-300",
    },
    {
      value: "average",
      label: "一般",
      description: "报告还可以，但有改进空间",
      icon: Meh,
      color: "text-yellow-600",
      bgColor: "bg-yellow-50 hover:bg-yellow-100 border-yellow-200",
      selectedBg: "bg-yellow-100 border-yellow-300",
    },
    {
      value: "not-valuable",
      label: "无价值",
      description: "这份报告对我没有帮助",
      icon: ThumbsDown,
      color: "text-red-600",
      bgColor: "bg-red-50 hover:bg-red-100 border-red-200",
      selectedBg: "bg-red-100 border-red-300",
    },
  ]

  const handleSubmit = async () => {
    if (!selectedRating) return

    setIsSubmitting(true)

    // Simulate API call
    await new Promise((resolve) => setTimeout(resolve, 1000))

    // Close dialog and trigger callback
    onOpenChange(false)
    onEvaluationComplete()

    // Reset state
    setSelectedRating(null)
    setIsSubmitting(false)
  }

  const handleClose = () => {
    onOpenChange(false)
    setSelectedRating(null)
  }

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle className="flex items-center space-x-2">
            <Star className="w-5 h-5 text-secondary" />
            <span>评价这份报告</span>
          </DialogTitle>
          <DialogDescription>您的反馈将帮助我们改进分析质量，请选择您对这份市场洞察报告的评价</DialogDescription>
        </DialogHeader>

        <div className="space-y-3 py-4">
          {evaluationOptions.map((option) => {
            const Icon = option.icon
            const isSelected = selectedRating === option.value

            return (
              <Card
                key={option.value}
                className={`cursor-pointer transition-all duration-200 border-2 ${
                  isSelected ? option.selectedBg : option.bgColor
                }`}
                onClick={() => setSelectedRating(option.value)}
              >
                <CardContent className="p-4">
                  <div className="flex items-center space-x-3">
                    <Icon className={`w-5 h-5 ${option.color}`} />
                    <div className="flex-1">
                      <h4 className="font-medium text-foreground">{option.label}</h4>
                      <p className="text-sm text-muted-foreground">{option.description}</p>
                    </div>
                    {isSelected && <div className="w-2 h-2 bg-secondary rounded-full" />}
                  </div>
                </CardContent>
              </Card>
            )
          })}
        </div>

        <div className="flex justify-end space-x-2 pt-4">
          <Button variant="outline" onClick={handleClose} disabled={isSubmitting}>
            跳过
          </Button>
          <Button onClick={handleSubmit} disabled={!selectedRating || isSubmitting}>
            {isSubmitting ? "提交中..." : "提交评价"}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  )
}
