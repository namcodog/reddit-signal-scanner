import { describe, it, expect } from 'vitest'
import {
  FeedbackSource,
  FeedbackEventType,
  RatingValue,
  InsightFlag,
  type FeedbackEventRequest,
  type AnalysisRatingEvent,
  type InsightFlagEvent,
  type MetricEvent,
  isAnalysisRatingEvent,
  isInsightFlagEvent,
  isMetricEvent,
} from '../../src/types/feedback'

describe('feedback contract types', () => {
  it('enums map to backend values', () => {
    expect(FeedbackSource.User).toBe('user')
    expect(FeedbackSource.Admin).toBe('admin')
    expect(FeedbackEventType.AnalysisRating).toBe('analysis_rating')
    expect(FeedbackEventType.InsightFlag).toBe('insight_flag')
    expect(FeedbackEventType.Metric).toBe('metric')
    expect(RatingValue.Like).toBe('like')
    expect(RatingValue.Dislike).toBe('dislike')
    expect(InsightFlag.Useful).toBe('useful')
  })

  it('discriminated union narrows correctly', () => {
    const e1: AnalysisRatingEvent = {
      source: FeedbackSource.User,
      event_type: FeedbackEventType.AnalysisRating,
      task_id: 't1',
      rating: RatingValue.Like,
    }
    const e2: InsightFlagEvent = {
      source: FeedbackSource.User,
      event_type: FeedbackEventType.InsightFlag,
      task_id: 't2',
      insight_id: 'ins_1',
      flag: InsightFlag.Useful,
    }
    const e3: MetricEvent = {
      source: FeedbackSource.User,
      event_type: FeedbackEventType.Metric,
      task_id: 't3',
      metric_name: 'dwell_seconds',
      metric_value: 12.5,
    }

    const list: FeedbackEventRequest[] = [e1, e2, e3]
    expect(list).toHaveLength(3)

    // Runtime guards mirror编译期约束
    expect(isAnalysisRatingEvent(e1)).toBe(true)
    expect(isInsightFlagEvent(e2)).toBe(true)
    expect(isMetricEvent(e3)).toBe(true)
  })
})
