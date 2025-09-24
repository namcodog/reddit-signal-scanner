import { useEffect, useState } from 'react';
import {
  getAnalysisSummary,
  AnalysisSummary,
  postAnalysisFeedback,
  trackAdminActionSuccess,
  trackAdminActionFail,
} from '../../services/adminApi';
import { useAdminSession } from '../../hooks/useAdminSession';
import { showToast } from '../../utils/toast';

export default function AdminAnalysisPage() {
  const [items, setItems] = useState<AnalysisSummary[]>([]);
  const [total, setTotal] = useState(0);
  const [q, setQ] = useState('');
  const [traceId, setTraceId] = useState<string | undefined>(undefined);
  const [pending, setPending] = useState<Record<string, boolean>>({});
  const { roles } = useAdminSession();
  const canRate = roles.includes('operations') || roles.includes('technical');
  const [lastDecision, setLastDecision] = useState<Record<string, string>>({});

  useEffect(() => {
    (async () => {
      const res = await getAnalysisSummary({ q, limit: 20 });
      setItems(res.data.items);
      setTotal(res.data.total);
      setTraceId(res.trace_id);
    })();
  }, [q]);

  async function onRate(taskId: string, satisfied: boolean) {
    const label = satisfied ? '满意' : '不满意';
    const previousLabel = lastDecision[taskId];
    setLastDecision(prev => ({ ...prev, [taskId]: label }));
    setPending(prev => ({ ...prev, [taskId]: true }));

    try {
      const res = await postAnalysisFeedback({ task_id: taskId, satisfied, reasons: [] });
      setTraceId(res.trace_id);
      await trackAdminActionSuccess(taskId, satisfied ? 'satisfied' : 'unsatisfied');
      showToast('反馈已记录', 'success');
    } catch (error: unknown) {
      const message = error instanceof Error ? error.message : '未知错误';
      if (previousLabel) {
        setLastDecision(prev => ({ ...prev, [taskId]: previousLabel }));
      } else {
        setLastDecision(prev => {
          const clone = { ...prev };
          delete clone[taskId];
          return clone;
        });
      }
      await trackAdminActionFail(taskId, 'rate', message);
      showToast(`反馈失败：${message}`, 'error');
    } finally {
      setPending(prev => {
        const clone = { ...prev };
        delete clone[taskId];
        return clone;
      });
    }
  }

  return (
    <div>
      <h2>Admin · Analysis {traceId ? <small style={{color:'#888'}}>trace_id: {traceId}</small> : null}</h2>
      <div style={{ display: 'flex', gap: 8 }}>
        <input placeholder="search task id" value={q} onChange={e => setQ(e.target.value)} />
        <span>total: {total}</span>
        {!canRate && <span style={{ color: '#c00' }}>只读模式（缺少权限）</span>}
      </div>
      <ul>
        {items.map(it => (
          <li key={it.task_id} style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
            <span>
              {it.task_id} · A-Score {it.a_score} · coverage {(it.coverage * 100).toFixed(0)}%
              {lastDecision[it.task_id] ? (
                <em style={{ marginLeft: 8, fontSize: 12, color: '#555' }}>
                  最近反馈: {lastDecision[it.task_id]}
                </em>
              ) : null}
            </span>
            <button
              disabled={!canRate || Boolean(pending[it.task_id])}
              onClick={() => onRate(it.task_id, true)}
            >
              {pending[it.task_id] ? '提交中…' : '满意'}
            </button>
            <button
              disabled={!canRate || Boolean(pending[it.task_id])}
              onClick={() => onRate(it.task_id, false)}
            >
              不满意
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}
