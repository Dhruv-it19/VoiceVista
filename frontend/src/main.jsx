import { useEffect, useRef, useState } from 'react';
import { createRoot } from 'react-dom/client';
import './styles.css';

const API_URL = (import.meta.env.VITE_API_URL || '').replace(/\/$/, '');
const fallbackLanguages = {
  en: 'English', hi: 'Hindi', es: 'Spanish', fr: 'French', de: 'German',
  gu: 'Gujarati', ur: 'Urdu', bn: 'Bengali', ta: 'Tamil', mr: 'Marathi', kn: 'Kannada'
};

function apiPath(path) {
  return `${API_URL}${path}`;
}

function mediaUrl(path) {
  if (!path) return '';
  return path.startsWith('http') ? path : `${API_URL}${path}`;
}

function App() {
  const [mode, setMode] = useState('upload');
  const [languages, setLanguages] = useState(fallbackLanguages);
  const [language, setLanguage] = useState('en');
  const [file, setFile] = useState(null);
  const [youtubeLink, setYoutubeLink] = useState('');
  const [status, setStatus] = useState('idle');
  const [error, setError] = useState('');
  const [result, setResult] = useState(null);
  const fileInputRef = useRef(null);

  useEffect(() => {
    fetch(apiPath('/api/languages'))
      .then((response) => response.ok ? response.json() : Promise.reject())
      .then(setLanguages)
      .catch(() => setLanguages(fallbackLanguages));
  }, []);

  function selectFile(candidate) {
    if (!candidate) return;
    if (!candidate.type.startsWith('video/')) {
      setError('Please choose a video file.');
      return;
    }
    setError('');
    setFile(candidate);
  }

  function handleDrop(event) {
    event.preventDefault();
    selectFile(event.dataTransfer.files[0]);
  }

  async function handleSubmit(event) {
    event.preventDefault();
    setError('');
    setResult(null);
    const formData = new FormData();
    formData.append('language', language);

    if (mode === 'upload') {
      if (!file) {
        setError('Choose a video before starting the translation.');
        return;
      }
      formData.append('video', file);
    } else {
      if (!youtubeLink.trim()) {
        setError('Paste a YouTube link before starting the translation.');
        return;
      }
      formData.append('youtube_link', youtubeLink.trim());
    }

    setStatus('processing');
    try {
      const response = await fetch(apiPath(`/api/translate/${mode}`), { method: 'POST', body: formData });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.detail || 'Translation failed.');
      setResult(payload);
      setStatus('complete');
    } catch (requestError) {
      setError(requestError.message || 'Unable to reach the translation service.');
      setStatus('idle');
    }
  }

  function startOver() {
    setResult(null);
    setError('');
    setStatus('idle');
    setFile(null);
    setYoutubeLink('');
  }

  return (
    <div className="app-shell">
      <header className="topbar">
        <a className="brand" href="/" aria-label="VoiceVista home">
          <span className="brand-mark">A</span>
          <span>VoiceVista</span>
        </a>
        <span className="service-status"><span className="status-dot" /> Translation workspace</span>
      </header>

      <main className="workspace">
        {status === 'complete' && result ? (
          <ResultView result={result} onStartOver={startOver} />
        ) : (
          <section className="translate-panel">
            <div className="intro">
              <span className="eyebrow">Voice translation</span>
              <h1>Turn spoken video into another language</h1>
              <p>Upload a video or paste a YouTube link. VoiceVista transcribes the speech, translates it, and returns a dubbed video.</p>
            </div>

            <div className="mode-switch" role="tablist" aria-label="Video source">
              <button className={mode === 'upload' ? 'active' : ''} onClick={() => setMode('upload')} role="tab" aria-selected={mode === 'upload'}>Upload video</button>
              <button className={mode === 'youtube' ? 'active' : ''} onClick={() => setMode('youtube')} role="tab" aria-selected={mode === 'youtube'}>YouTube link</button>
            </div>

            <form onSubmit={handleSubmit}>
              {mode === 'upload' ? (
                <div className={`drop-zone ${file ? 'has-file' : ''}`} onClick={() => fileInputRef.current?.click()} onDrop={handleDrop} onDragOver={(event) => event.preventDefault()} role="button" tabIndex="0" onKeyDown={(event) => event.key === 'Enter' && fileInputRef.current?.click()}>
                  <input ref={fileInputRef} type="file" accept="video/*" hidden onChange={(event) => selectFile(event.target.files[0])} />
                  <span className="drop-icon">{file ? '✓' : '↑'}</span>
                  <strong>{file ? file.name : 'Drop a video here or browse your files'}</strong>
                  <span>{file ? 'Click to choose a different video' : 'MP4, AVI, MOV, or WEBM'}</span>
                </div>
              ) : (
                <label className="field">
                  <span>YouTube video link</span>
                  <input type="url" value={youtubeLink} onChange={(event) => setYoutubeLink(event.target.value)} placeholder="https://www.youtube.com/watch?v=..." />
                </label>
              )}

              <label className="field">
                <span>Translate voice to</span>
                <select value={language} onChange={(event) => setLanguage(event.target.value)}>
                  {Object.entries(languages).map(([code, name]) => <option key={code} value={code}>{name}</option>)}
                </select>
              </label>

              {mode === 'youtube' && <p className="hint">Short, public videos usually process fastest. Live streams and restricted videos may not be available.</p>}
              {error && <p className="error-message" role="alert">{error}</p>}

              <button className="primary-action" type="submit" disabled={status === 'processing'}>
                {status === 'processing' ? <><span className="spinner" /> Preparing translation...</> : <>Translate video <span>→</span></>}
              </button>
            </form>
          </section>
        )}
      </main>
    </div>
  );
}

function ResultView({ result, onStartOver }) {
  return (
    <section className="result-panel">
      <div className="result-heading">
        <span className="success-mark">✓</span>
        <div><span className="eyebrow">Ready to review</span><h1>Your translated video is ready</h1></div>
      </div>
      <div className="video-grid">
        <VideoCard title="Original video" source={result.original_video_url} />
        <VideoCard title="Translated video" source={result.translated_video_url} accent />
      </div>
      <div className="transcript-grid">
        <article><span>Original transcript</span><p>{result.original_text || 'No transcript returned.'}</p></article>
        <article><span>Translated transcript</span><p>{result.translated_text || 'No translated transcript returned.'}</p></article>
      </div>
      <div className="result-actions">
        <a className="primary-action inline" href={mediaUrl(result.translated_video_url)} download>Download video <span>↓</span></a>
        <button className="secondary-action" onClick={onStartOver}>Translate another</button>
      </div>
    </section>
  );
}

function VideoCard({ title, source, accent = false }) {
  return <article className={`video-card ${accent ? 'accent' : ''}`}><h2>{title}</h2>{source ? <video controls src={mediaUrl(source)} /> : <div className="video-missing">Video unavailable</div>}</article>;
}

createRoot(document.getElementById('root')).render(<App />);
