import { useEffect, useState } from 'react';
import { getFeedbackSummary, exportFeedback, trackExportClicked, trackAdminActionFail } from '../../services/adminApi';
import { useAdminSession } from '../../hooks/useAdminSession';
import { showToast } from '../../utils/toast';

export default function AdminFeedbackPage() {
  const [days, setDays] = useState(30);
  const [data, setData] = useState<{ total:number; likes:number; dislikes:number; top_reasons:{reason:string;count:number}[] } | null>(null);
  const [traceId, setTraceId] = useState<string | undefined>(undefined);
  const { roles } = useAdminSession();
  const canExport = roles.includes('operations') || roles.includes('technical');

  useEffect(() => {
    (async () => {
      const res = await getFeedbackSummary(days);
      setData(res.data);
      setTraceId(res.trace_id);
    })();
  }, [days]);

  async function onExport(format: 'json' | 'csv') {
    try {
      await trackExportClicked();
      const { contentType, body } = await exportFeedback(format, { limit: 1000 });
      if (format === 'csv' || contentType.startsWith('text/csv')) {
        const blob = new Blob([body], { type: 'text/csv;charset=utf-8;' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `feedback_export_${Date.now()}.csv`;
        a.click();
        URL.revokeObjectURL(url);
        showToast('CSV 导出已开始下载', 'success');
      } else {
        try {
          const obj = JSON.parse(body);
          showToast(`导出完成，共 ${obj.count ?? 0} 条`, 'success');
        } catch {
          showToast('导出完成', 'success');
        }
      }
    } catch (error: unknown) {
      const message = error instanceof Error ? error.message : '未知错误';
      await trackAdminActionFail('admin', 'export', message);
      showToast(`导出失败：${message}`, 'error');
    }
  }

  return (
    <div>
      <h2>Admin · Feedback {traceId ? <small style={{color:'#888'}}>trace_id: {traceId}</small> : null}</h2>
      <div>
        <label>days: </label>
        <input type="number" value={days} onChange={e => setDays(parseInt(e.target.value || '30', 10))} />
        <button disabled={!canExport} onClick={() => onExport('json')} style={{ marginLeft: 8 }}>导出 JSON</button>
        <button disabled={!canExport} onClick={() => onExport('csv')} style={{ marginLeft: 8 }}>导出 CSV</button>
        {!canExport && <span style={{ marginLeft: 12, color: '#c00' }}>只读模式（无导出权限）</span>}
      </div>
      {data && (
        <div>
          <div>total: {data.total} · likes: {data.likes} · dislikes: {data.dislikes}</div>
          <ul>
            {data.top_reasons.map((r, idx) => (
              <li key={idx}>{r.reason} · {r.count}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
