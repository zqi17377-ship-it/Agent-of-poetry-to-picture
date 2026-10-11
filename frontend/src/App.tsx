import {useEffect, useRef, useState} from 'react';
import {ArrowLeft, ArrowUpRight, Check, ChevronDown, Download, Feather, History, LoaderCircle, Plus, Settings2, Sparkles, X} from 'lucide-react';
import {api, imageUrl, type Artwork, type Config, type HistoryItem, type Job, type Version} from './api';
import {readJobSnapshot} from './jobSync';

const examples = [
  {label: '雨后的湖岸', text: 'The rain has left the lake.\nUnder the grey sky, the water holds the silence of the shore.'},
  {label: '冬日与独处', text: 'I walk alone through the winter trees.\nThe snow keeps the shape of every silence.'},
  {label: '温暖的晨光', text: 'Warm sunlight rests on the grass.\nFor a moment, the world asks for nothing.'},
];
const stages: Record<string, string> = {queued: '等待生成', analyzing: '正在理解文字', designing: '正在构思画面', generating: '正在生成画面', checking: '正在检查图片', saving: '正在保存作品', done: '作品已保存'};
const active = (job?: Job | null) => !!job && ['queued', 'running'].includes(job.status);
const readableDate = (value: string) => new Date(value).toLocaleDateString('zh-CN', {month: 'short', day: 'numeric'});

export default function App() {
  const [text, setText] = useState('');
  const [title, setTitle] = useState('');
  const [author, setAuthor] = useState('');
  const [ratio, setRatio] = useState('3:2');
  const [config, setConfig] = useState<Config | null>(null);
  const [artwork, setArtwork] = useState<Artwork | null>(null);
  const [versionId, setVersionId] = useState('');
  const [job, setJob] = useState<Job | null>(null);
  const [history, setHistory] = useState<HistoryItem[]>([]);
  const [page, setPage] = useState<'create' | 'history'>('create');
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [revisionOpen, setRevisionOpen] = useState(false);
  const [revision, setRevision] = useState('');
  const [error, setError] = useState('');
  const [pollError, setPollError] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const submittingRef = useRef(false);
  const selectedRef = useRef('');
  const textRef = useRef<HTMLTextAreaElement>(null);
  const resultRef = useRef<HTMLElement>(null);
  const settingsRef = useRef<HTMLElement>(null);
  const busy = submitting || active(job);
  const version: Version | undefined = artwork?.versions.find(v => v.id === versionId) ?? artwork?.versions.at(-1);

  async function loadArtwork(id: string, restoreInput = false) {
    const loaded = await api<Artwork>('/artworks/' + id);
    showArtwork(loaded, restoreInput);
  }

  function showArtwork(loaded: Artwork, restoreInput = false) {
    if (selectedRef.current !== loaded.id) return;
    setArtwork(loaded);
    setVersionId(loaded.versions.at(-1)?.id ?? '');
    setJob(loaded.jobs.at(-1) ?? null);
    if (restoreInput) {setText(loaded.text); setTitle(loaded.title); setAuthor(loaded.author); setRatio(loaded.aspect_ratio);}
    localStorage.setItem('yujing-artwork', loaded.id);
  }

  async function refreshHistory() {setHistory(await api<HistoryItem[]>('/artworks'));}

  useEffect(() => {
    if (!settingsOpen) return;
    const previousFocus = document.activeElement as HTMLElement | null;
    const panel = settingsRef.current;
    const focusable = () => Array.from(panel?.querySelectorAll<HTMLElement>('button:not(:disabled), a[href], input:not(:disabled), select:not(:disabled), summary') ?? []);
    focusable()[0]?.focus();
    function onKey(event: KeyboardEvent) {
      if (event.key === 'Escape') {event.preventDefault(); setSettingsOpen(false);}
      if (event.key === 'Tab') {
        const elements = focusable();
        const first = elements[0], last = elements.at(-1);
        if (!panel?.contains(document.activeElement) || (event.shiftKey && document.activeElement === first)) {event.preventDefault(); (event.shiftKey ? last : first)?.focus();}
        else if (!event.shiftKey && document.activeElement === last) {event.preventDefault(); first?.focus();}
      }
    }
    document.addEventListener('keydown', onKey);
    return () => {document.removeEventListener('keydown', onKey); previousFocus?.focus();};
  }, [settingsOpen]);

  useEffect(() => {
    let disposed = false;
    (async () => {
      try {
        const [initialConfig, initialHistory] = await Promise.all([api<Config>('/config'), api<HistoryItem[]>('/artworks')]);
        if (disposed) return;
        setConfig(initialConfig); setHistory(initialHistory);
        const last = localStorage.getItem('yujing-artwork');
        if (last) {
          selectedRef.current = last;
          try {await loadArtwork(last, true);} catch {localStorage.removeItem('yujing-artwork'); selectedRef.current = '';}
        }
      } catch (error) {if (!disposed) setError((error as Error).message);}
    })();
    return () => {disposed = true;};
  }, []);

  useEffect(() => {
    if (!job) return;
    let disposed = false;
    let timer: ReturnType<typeof setTimeout>;
    const expectedId = job.artwork_id;
    async function poll() {
      try {
        const snapshot = await readJobSnapshot(job!.id, api);
        const updated = snapshot.job;
        if (disposed || selectedRef.current !== expectedId) return;
        setPollError(false);
        if (snapshot.artwork) {
          showArtwork(snapshot.artwork);
          refreshHistory().catch(() => {});
          if (updated.status === 'succeeded' && active(job)) setTimeout(() => {if (selectedRef.current === expectedId) resultRef.current?.scrollIntoView({behavior: 'smooth', block: 'start'});}, 100);
        } else {setJob(updated); timer = setTimeout(poll, 1400);}
      } catch {if (!disposed && selectedRef.current === expectedId) {setPollError(true); timer = setTimeout(poll, 3000);}}
    }
    timer = setTimeout(poll, 500);
    return () => {disposed = true; clearTimeout(timer);};
  }, [job?.id]);

  async function generate() {
    if (submittingRef.current || busy) return;
    if (!text.trim() || text.trim().length > 8000) {setError('请输入 1–8000 字的诗文。'); textRef.current?.focus(); return;}
    submittingRef.current = true; setSubmitting(true); setError(''); setPollError(false);
    try {
      const result = await api<{artwork_id: string; job_id: string}>('/artworks', {text, title, author, aspect_ratio: ratio});
      selectedRef.current = result.artwork_id;
      setRevisionOpen(false); setRevision('');
      await loadArtwork(result.artwork_id);
      await refreshHistory();
    } catch (error) {setError((error as Error).message);}
    finally {submittingRef.current = false; setSubmitting(false);}
  }

  async function modify() {
    if (!artwork || !version || !revision.trim() || submittingRef.current || busy) return;
    const expectedId = artwork.id;
    submittingRef.current = true; setSubmitting(true); setError('');
    try {
      const result = await api<{job_id: string}>(`/artworks/${artwork.id}/revisions`, {source_version_id: version.id, instruction: revision, mode: config?.supports_edit ? 'edit' : 'regenerate'});
      const updated = await api<Job>('/jobs/' + result.job_id);
      if (selectedRef.current === expectedId) {setJob(updated); setRevisionOpen(false); setRevision('');}
    } catch (error) {if (selectedRef.current === expectedId) setError((error as Error).message);}
    finally {submittingRef.current = false; setSubmitting(false);}
  }

  function startNew() {
    selectedRef.current = ''; localStorage.removeItem('yujing-artwork');
    setArtwork(null); setJob(null); setVersionId(''); setText(''); setTitle(''); setAuthor('');
    setRevision(''); setRevisionOpen(false); setError(''); setPage('create');
    setTimeout(() => textRef.current?.focus(), 0);
  }

  async function openHistory(id: string) {
    selectedRef.current = id; setPage('create'); setError(''); setRevisionOpen(false);
    try {await loadArtwork(id, true);} catch (error) {setError((error as Error).message);}
  }

  return <div className="app-shell">
    <header className="site-header">
      <button className="brand" onClick={() => setPage('create')} aria-label="余境首页"><span className="brand-mark"><Feather size={21} strokeWidth={1.4}/></span><span>余境<span className="brand-caption">VERSE TO SCENERY</span></span></button>
      <nav aria-label="主导航"><button className={page === 'create' ? 'nav-link current' : 'nav-link'} onClick={() => setPage('create')}>创作</button><button className={page === 'history' ? 'nav-link current' : 'nav-link'} onClick={() => {setPage('history'); refreshHistory().catch(e => setError(e.message));}}><History size={15}/><span>我的作品</span></button><button className="icon-button settings-trigger" onClick={() => setSettingsOpen(true)} aria-label="模型接入设置"><Settings2 size={19}/></button></nav>
    </header>
    <main>
      {page === 'history' ? <section className="history-page">
        <div className="section-heading"><div><span className="eyebrow">YOUR COLLECTION</span><h1>留住的风景</h1><p>文字与画面，以及每一次新的尝试。</p></div><button className="secondary" onClick={startNew}><Plus size={16}/>新的创作</button></div>
        {history.length ? <div className="history-grid">{history.map(item => <button className="history-card" key={item.id} onClick={() => openHistory(item.id)}>{item.latest_version ? <img src={imageUrl(item.latest_version.id)} alt={item.title} loading="lazy"/> : <div className="history-placeholder"><Feather size={28} strokeWidth={1}/><span>{['queued', 'running'].includes(item.status) ? '画面正在生成' : '文字已保存'}</span></div>}<div className="history-caption"><span>{item.title}</span><small>{readableDate(item.created_at)}<ArrowUpRight size={15}/></small></div></button>)}</div> : <div className="empty-history"><Feather size={34} strokeWidth={1}/><h2>第一处风景，等待你的文字。</h2><button className="primary" onClick={startNew}>开始创作<ArrowUpRight size={16}/></button></div>}
      </section> : <>
        <section className="intro"><span className="eyebrow"><span className="tiny-line"/> A PLACE BETWEEN WORDS AND IMAGES</span><h1>把诗意，留在画面里<span className="heading-dot">。</span></h1><p>写下一段触动你的文字，<br className="mobile-break"/>让情绪与意象成为一处风景。</p></section>
        <section className="writing-card" aria-label="诗文输入">
          <div className="card-label"><label htmlFor="poem">你的文字</label><span><span className="status-dot"/>{config?.free_demo ? '免费模型 · FLUX' : '自然写实 · 自动构图'}</span></div>
          <textarea ref={textRef} id="poem" value={text} onChange={e => {setText(e.target.value); setError('');}} placeholder={'在这里粘贴一首诗，或一段散文……\n\n原文与中文译文都可以。'} maxLength={8000} disabled={busy} spellCheck={false}/>
          <details className="more-options"><summary>更多选项<ChevronDown size={14}/></summary><div className="option-fields"><label>作品名称<input value={title} onChange={e => setTitle(e.target.value)} placeholder="可留空" maxLength={200} disabled={busy}/></label><label>作者<input value={author} onChange={e => setAuthor(e.target.value)} placeholder="可留空" maxLength={200} disabled={busy}/></label><label>图片比例<select value={ratio} onChange={e => setRatio(e.target.value)} disabled={busy}><option value="3:2">横幅 · 3:2</option><option value="1:1">方形 · 1:1</option><option value="2:3">竖幅 · 2:3</option></select></label></div></details>
          <div className="writing-toolbar"><span className="input-note">氛围、光线与构图，由文字决定{config?.text_provider === 'basic' && <span className="basic-mode-note">基础理解 · 复杂隐喻可接入语言模型</span>}<span className="char-count">{text.length.toLocaleString()} / 8,000</span></span><button className="primary" disabled={busy || !text.trim() || !config} onClick={generate}>{busy ? <LoaderCircle size={16} className="spin"/> : <Sparkles size={16}/>}<span>{busy ? '创作中' : artwork ? '重新生成' : '生成图片'}</span><ArrowUpRight size={15}/></button></div>
        </section>
        {!artwork && <div className="examples"><span>试一段示例</span>{examples.map(example => <button key={example.label} disabled={busy} onClick={() => {setText(example.text); textRef.current?.focus();}}>{example.label}<ArrowUpRight size={12}/></button>)}</div>}
        {error && <p className="error-banner" role="alert">{error}</p>}
        {active(job) && <div className="progress-card" role="status" aria-live="polite"><span className="progress-icon"><LoaderCircle size={20} className="spin"/></span><div><strong>{pollError ? '暂时连接不上，正在恢复状态' : stages[job?.stage ?? 'queued'] ?? '正在创作'}</strong><p>{config?.free_demo ? '免费服务可能需要排队。你可以离开页面，回来后继续查看。' : '你的文字与创作过程会自动保存。'}</p></div><span className="progress-dots"><i/><i/><i/></span></div>}
        {job && ['failed', 'needs_review'].includes(job.status) && <div className="error-banner" role="alert"><strong>{job.status === 'needs_review' ? '这次生成需要核查' : '这次生成没有完成'}</strong><p>{job.error}</p>{job.provider_request_id && <details><summary>查看任务编号</summary><code>{job.provider_request_id}</code></details>}</div>}
        {version && <section className="result-section" ref={resultRef} aria-label="生成的作品"><div className="result-heading"><div><span className="eyebrow">A SCENE FROM YOUR WORDS</span><h2>{artwork?.title}</h2></div><span className="saved-label"><Check size={13}/>已自动保存</span></div><div className="result-image"><img src={imageUrl(version.id)} alt={artwork?.title || '根据诗文生成的意境图'}/></div><div className="result-toolbar"><span>{version.interpretation.emotions.slice(0, 3).join(' · ')}<small>{version.model}</small></span><div><button className="secondary" disabled={busy} onClick={() => setRevisionOpen(!revisionOpen)}><Settings2 size={15}/>{config?.supports_edit ? '调整画面' : '调整后重画'}</button><a className="primary" href={imageUrl(version.id, true)} download><Download size={15}/>下载原图</a></div></div>
          {revisionOpen && <form className="revision-form" onSubmit={e => {e.preventDefault(); modify();}}><label htmlFor="revision">想让画面有什么变化？</label><div><input id="revision" value={revision} onChange={e => setRevision(e.target.value)} placeholder="例如：光线更柔和，雾再薄一点" maxLength={2000} autoFocus/><button className="primary" disabled={busy || !revision.trim()} type="submit">{config?.supports_edit ? '应用修改' : '重新生成'}<ArrowUpRight size={15}/></button></div><p>{config?.supports_edit ? '以这张图片为参考，生成一个新的版本。' : '当前免费模型会按新描述重新生成，构图可能变化。已有图片会保留。'}</p></form>}
          <details className="creation-details"><summary>这幅画面如何理解文字<ChevronDown size={14}/></summary><p>{version.brief.rationale}</p>{version.interpretation.imagery.length > 0 && <div className="imagery-tags">{version.interpretation.imagery.map((item, i) => <span key={i}>“{item.source_quote}”</span>)}</div>}<p className="muted">{version.interpretation.ambiguities.join(' ')}</p>{version.brief.additions.length > 0 && <p className="muted">创作补充：{version.brief.additions.join('；')}</p>}<p className="muted">{version.quality_report.flags.join('；') || version.quality_report.rationale}</p></details>
          {artwork && artwork.versions.length > 1 && <details className="creation-details"><summary>查看历史版本 · {artwork.versions.length}<ChevronDown size={14}/></summary><div className="version-list">{artwork.versions.map((item, i) => <button className={item.id === version.id ? 'version-thumb selected' : 'version-thumb'} onClick={() => setVersionId(item.id)} key={item.id}><img src={imageUrl(item.id)} alt={`版本 ${i + 1}`} loading="lazy"/><span>版本 {i + 1}</span></button>)}</div></details>}
          {artwork && <details className="creation-details"><summary>查看调用记录<ChevronDown size={14}/></summary>{artwork.jobs.map(item => <p className="muted" key={item.id}>{readableDate(artwork.created_at)} · {item.call_count} 次模型请求 · {(item.elapsed_ms / 1000).toFixed(1)} 秒 · {item.status === 'succeeded' ? '完成' : item.status === 'failed' ? '失败' : item.status === 'needs_review' ? '需核查' : '处理中'}</p>)}</details>}
          <button className="new-artwork-button" disabled={busy} onClick={startNew}><Plus size={16}/>开始一段新的创作</button>
        </section>}
        {!artwork && <div className="quiet-note"><span>理解文字</span><i/><span>构思画面</span><i/><span>留住意境</span></div>}
      </>}
    </main>
    <footer><span>余境 <span className="footer-divider">/</span> 文字之外，还有风景。</span><span>{config?.free_demo ? '免费试用 · 共享额度与队列' : '诗文意境创作工具'}</span></footer>
    {settingsOpen && <div className="modal-backdrop" onClick={() => setSettingsOpen(false)}><section ref={settingsRef} className="settings-panel" role="dialog" aria-modal="true" aria-labelledby="settings-title" onClick={e => e.stopPropagation()} onKeyDown={e => {if (e.key === 'Escape') setSettingsOpen(false);}}><div className="panel-heading"><h2 id="settings-title">模型接入</h2><button className="icon-button" onClick={() => setSettingsOpen(false)} aria-label="关闭设置"><X size={19}/></button></div><p className="muted">创作界面保持简单，模型服务可以随时替换。</p><div className="connection-row"><span>图像生成</span><strong>{config?.image_provider === 'hf_space' ? 'FLUX.1-schnell · 免费演示' : config?.image_provider === 'gemini' ? 'Gemini 图像 API' : '自定义兼容 API'}</strong></div><div className="connection-row"><span>文学理解</span><strong>{config?.text_provider === 'basic' ? '基础意象提取' : config?.text_provider === 'gemini' ? 'Gemini 语言模型' : '自定义语言模型'}</strong></div><div className="settings-note"><strong>免费调试模式</strong><p>公共演示无需密钥即可尝试，有每日额度和排队限制。基础理解擅长提取明显意象，复杂隐喻建议接入语言模型。</p></div><details className="connection-help"><summary>如何更换 API 服务<ChevronDown size={14}/></summary><p>将项目中的 <code>.env.example</code> 复制为 <code>.env</code>，填写服务类型、地址、模型名称与密钥，再重启应用。</p><p>支持免费 FLUX 演示、Gemini，以及提供 <code>chat/completions</code> 或 <code>images/generations</code> 的兼容服务。文字理解与图像生成可分别配置。</p><p>密钥仅由本机后端读取，不会显示在页面上。</p></details><button className="secondary panel-close" onClick={() => setSettingsOpen(false)}><ArrowLeft size={15}/>返回创作</button></section></div>}
  </div>;
}
