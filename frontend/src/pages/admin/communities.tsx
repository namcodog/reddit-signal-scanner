import { useEffect, useState } from 'react';
import {
  getCommunitiesSummary,
  CommunitySummary,
  StatusColor,
  postCommunityDecision,
  type CommunityAction,
  trackAdminActionSuccess,
  trackAdminActionFail,
} from '../../services/adminApi';
import { useAdminSession } from '../../hooks/useAdminSession';
import { showToast } from '../../utils/toast';

export default function AdminCommunitiesPage() {
  const [items, setItems] = useState<CommunitySummary[]>([]);
  const [total, setTotal] = useState(0);
  const [q, setQ] = useState('');
  const [status, setStatus] = useState<StatusColor | ''>('');
  const [traceId, setTraceId] = useState<string | undefined>(undefined);
  const [pending, setPending] = useState<Record<string, boolean>>({});
  const { roles } = useAdminSession();
  const canOperate = roles.includes('operations');
  const [lastAction, setLastAction] = useState<Record<string, string>>({});

  useEffect(() => {
    (async () => {
      const res = await getCommunitiesSummary({ q, status: status || undefined, limit: 20 });
      setItems(res.data.items);
      setTotal(res.data.total);
      setTraceId(res.trace_id);
    })();
  }, [q, status]);

  async function onDecision(community: string, action: CommunityAction) {
    const index = items.findIndex(it => it.community === community);
    if (index === -1) {
      return;
    }

    const previous = items[index];
    const optimistic: CommunitySummary = { ...previous };
    if (action === 'approve') {
      optimistic.status_color = 'green';
    } else if (action === 'experiment') {
      optimistic.status_color = 'yellow';
    } else {
      optimistic.status_color = 'red';
    }

    setItems(prev => {
      const clone = [...prev];
      const idx = clone.findIndex(it => it.community === community);
      if (idx !== -1) {
        clone[idx] = optimistic;
      }
      return clone;
    });
    setPending(prev => ({ ...prev, [community]: true }));
    const prevLabel = lastAction[community];
    setLastAction(prev => ({ ...prev, [community]: action }));

    try {
      const res = await postCommunityDecision({ community, action });
      setTraceId(res.trace_id);
      await trackAdminActionSuccess(community, action);
      showToast('操作成功', 'success');
    } catch (error: unknown) {
      const message = error instanceof Error ? error.message : '未知错误';
      setItems(prev => {
        const clone = [...prev];
        const idx = clone.findIndex(it => it.community === community);
        if (idx !== -1) {
          clone[idx] = previous;
        }
        return clone;
      });
      if (prevLabel) {
        setLastAction(prev => ({ ...prev, [community]: prevLabel }));
      } else {
        setLastAction(prev => {
          const clone = { ...prev };
          delete clone[community];
          return clone;
        });
      }
      await trackAdminActionFail(community, action, message);
      showToast(`操作失败：${message}`, 'error');
    } finally {
      setPending(prev => {
        const clone = { ...prev };
        delete clone[community];
        return clone;
      });
    }
  }

  return (
    <div>
      <h2>Admin · Communities {traceId ? <small style={{color:'#888'}}>trace_id: {traceId}</small> : null}</h2>
      <div style={{ display: 'flex', gap: 8 }}>
        <input placeholder="search community" value={q} onChange={e => setQ(e.target.value)} />
        <select value={status} onChange={e => setStatus(e.target.value as StatusColor | '')}>
          <option value="">all</option>
          <option value="green">green</option>
          <option value="yellow">yellow</option>
          <option value="red">red</option>
        </select>
        <span>total: {total}</span>
        {!canOperate && <span style={{ color: '#c00' }}>只读模式（缺少运营权限）</span>}
      </div>
      <ul>
        {items.map(it => (
          <li key={it.community} style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
            <span>
              {it.community} · score {it.c_score} · {it.status_color} · hit7d {it.hit_7d}
              {lastAction[it.community] ? (
                <em style={{ marginLeft: 8, fontSize: 12, color: '#555' }}>
                  最后操作: {lastAction[it.community]}
                </em>
              ) : null}
            </span>
            <button
              disabled={!canOperate || Boolean(pending[it.community])}
              onClick={() => onDecision(it.community, 'approve')}
            >
              {pending[it.community] ? '处理中…' : '通过'}
            </button>
            <button
              disabled={!canOperate || Boolean(pending[it.community])}
              onClick={() => onDecision(it.community, 'experiment')}
            >
              实验
            </button>
            <button
              disabled={!canOperate || Boolean(pending[it.community])}
              onClick={() => onDecision(it.community, 'pause')}
            >
              暂停
            </button>
            <button
              disabled={!canOperate || Boolean(pending[it.community])}
              onClick={() => onDecision(it.community, 'blacklist')}
            >
              黑名单
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}
