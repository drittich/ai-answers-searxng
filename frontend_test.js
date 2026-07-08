
(async () => {
    const is_interactive = true;
    const q_init = "dummy_query";
    const lang_init = "en";
    let urls = [];
    const b64_init = "YmFzZTY0";
    const tk_init = "dummy_token";
    const script_root = "/searxng";
    const conversation = {
        originalQuery: q_init,
        originalContext: new TextDecoder().decode(Uint8Array.from(atob(b64_init), c => c.charCodeAt(0))),
        originalSources: [...urls],
        turns: [{role: 'user', content: q_init, ts: Date.now()}]
    };
    const is_collapsed = true;
    const url_state = true;
    const box = document.getElementById('sxng-stream-box');
    const data = document.getElementById('sxng-stream-data');
    const answerWrap = document.getElementById('sxng-answer-wrap');
    const showMoreWrap = document.getElementById('sxng-show-more-wrap');
    let restored = false;
    let isStreaming = false;

    function expandAnswer() {
        if (answerWrap) answerWrap.classList.remove('sxng-collapsed');
        if (showMoreWrap) showMoreWrap.classList.remove('sxng-visible');
    }
    function updateShowMore() {
        if (!is_collapsed || !answerWrap || !showMoreWrap) return;
        if (!answerWrap.classList.contains('sxng-collapsed')) return;
        if (answerWrap.scrollHeight > answerWrap.clientHeight + 4) {
            showMoreWrap.classList.add('sxng-visible');
        } else {
            // Content fits within the reserved height: release it (only ever shrinks).
            expandAnswer();
        }
    }
    const showMoreBtn = document.getElementById('sxng-show-more');
    if (showMoreBtn) showMoreBtn.onclick = expandAnswer;
    
    
                        // Only http(s) URLs may become citation links; anything else
                        // (javascript:, data:, non-strings) is neutralized to ''.
                        function safeCitationUrl(u) {
                            return (typeof u === 'string' && /^https?:\/\//i.test(u.trim())) ? u : '';
                        }

                        function renderCitations(text, urls) {
                            const fragment = document.createDocumentFragment();
                            const re = /\[(\d{1,2}(?:\s*,\s*\d{1,2})*)\]/g;
                            let lastIdx = 0;
                            const matches = [...text.matchAll(re)];
                            
                            matches.forEach(match => {
                                if (match.index > lastIdx) {
                                    const s = document.createElement('span');
                                    s.className = 'sxng-chunk';
                                    s.textContent = text.substring(lastIdx, match.index);
                                    fragment.appendChild(s);
                                }
                                match[1].split(/\s*,\s*/).forEach(n => {
                                    const idx = parseInt(n.trim());
                                    if (idx >= 1 && idx <= urls.length) {
                                        const url = safeCitationUrl(urls[idx-1]);
                                        if (url) {
                                            const a = document.createElement('a');
                                            a.href = url;
                                            a.target = '_blank';
                                            a.style.cssText = 'text-decoration:none;color:var(--color-result-link);font-weight:bold;';
                                            a.textContent = `[${n.trim()}]`;
                                            a.className = 'sxng-chunk';
                                            fragment.appendChild(a);
                                        } else {
                                            const s = document.createElement('span');
                                            s.className = 'sxng-chunk';
                                            s.textContent = `[${n.trim()}]`;
                                            fragment.appendChild(s);
                                        }
                                    } else {
                                        const s = document.createElement('span');
                                        s.className = 'sxng-chunk';
                                        s.textContent = `[${n.trim()}]`;
                                        fragment.appendChild(s);
                                    }
                                });
                                lastIdx = match.index + match[0].length;
                            });
                            
                            if (lastIdx < text.length) {
                                const s = document.createElement('span');
                                s.className = 'sxng-chunk';
                                // Preserve whitespace by not trimming
                                s.textContent = text.substring(lastIdx);
                                fragment.appendChild(s);
                            }
                            return fragment;
                        }

                        // Inline markdown (bold/italic/code) -> DOM, citations linkified in text runs.
                        function renderInline(text, urls, parent) {
                            const re = /\*\*([^*\n]+)\*\*|\*([^*\n]+)\*|`([^`\n]+)`/g;
                            let last = 0, m;
                            while ((m = re.exec(text)) !== null) {
                                if (m.index > last) parent.appendChild(renderCitations(text.substring(last, m.index), urls));
                                let el;
                                if (m[1] !== undefined) {
                                    el = document.createElement('strong');
                                    el.appendChild(renderCitations(m[1], urls));
                                } else if (m[2] !== undefined) {
                                    el = document.createElement('em');
                                    el.appendChild(renderCitations(m[2], urls));
                                } else {
                                    el = document.createElement('code');
                                    el.textContent = m[3];
                                }
                                parent.appendChild(el);
                                last = m.index + m[0].length;
                            }
                            if (last < text.length) parent.appendChild(renderCitations(text.substring(last), urls));
                        }

                        // Minimal block markdown: headers, ul/ol lists, paragraphs. All text is
                        // DOM-built (never innerHTML), so model output cannot inject markup.
                        function renderMarkdown(text, urls) {
                            const frag = document.createDocumentFragment();
                            let list = null, listType = null;
                            const closeList = () => { if (list) { frag.appendChild(list); list = null; listType = null; } };
                            text.split('\n').forEach(line => {
                                const t = line.trim();
                                const h = t.match(/^(#{1,4})\s+(.*)$/);
                                const ul = t.match(/^[-*+]\s+(.*)$/);
                                const ol = t.match(/^\d+[.)]\s+(.*)$/);
                                if (!t) {
                                    closeList();
                                } else if (h) {
                                    closeList();
                                    const el = document.createElement('div');
                                    el.className = 'sxng-md-h';
                                    renderInline(h[2], urls, el);
                                    frag.appendChild(el);
                                } else if (ul || ol) {
                                    const type = ul ? 'ul' : 'ol';
                                    if (!list || listType !== type) {
                                        closeList();
                                        list = document.createElement(type);
                                        list.className = 'sxng-md-list';
                                        listType = type;
                                    }
                                    const li = document.createElement('li');
                                    renderInline((ul || ol)[1], urls, li);
                                    list.appendChild(li);
                                } else {
                                    closeList();
                                    const p = document.createElement('div');
                                    p.className = 'sxng-md-p';
                                    renderInline(t, urls, p);
                                    frag.appendChild(p);
                                }
                            });
                            closeList();
                            return frag;
                        }


    
                        const footer = document.getElementById('sxng-footer');
                        const input = document.getElementById('sxng-action-input');
                        if (window.getComputedStyle && box) {
                            try {
                                const docStyles = getComputedStyle(document.documentElement);
                                let accent = docStyles.getPropertyValue('--color-result-link').trim();
                                if (!accent) {
                                    const a = document.createElement('a');
                                    document.body.appendChild(a);
                                    accent = getComputedStyle(a).color;
                                    document.body.removeChild(a);
                                }
                                if (accent) {
                                    box.style.setProperty('--color-result-link', accent);
                                    box.style.setProperty('--sxng-ai-accent', accent);
                                }
                            } catch(e) {}
                        }

                        // conversation saved as base64 URL fragment.
                        const updateState = () => {
                            if (!url_state) return;
                            try {
                                let state = {
                                    t: conversation.turns.map(t => ({
                                        r: t.role === 'user' ? 'u' : 'a',
                                        c: t.content.replace(/\s+/g, ' ').trim()
                                    })),
                                    u: urls
                                };
                                const encodeB64 = (obj) => {
                                    const u8 = new TextEncoder().encode(JSON.stringify(obj));
                                    let bin = '';
                                    // Use a loop to avoid RangeError: Maximum call stack size exceeded
                                    for (let i = 0; i < u8.byteLength; i++) {
                                        bin += String.fromCharCode(u8[i]);
                                    }
                                    return btoa(bin);
                                };
                                
                                let b64 = encodeB64(state);
                                while (b64.length > 2000 && state.t.length > 2) {
                                    state.t.splice(1, 2); // Delete in Q&A pairs
                                    b64 = encodeB64(state);
                                }
                                
                                history.replaceState(null, null, '#ai=' + b64);
                            } catch(e) {}
                        };

                        if (url_state && location.hash.includes('ai=')) {
                            try {
                                const b64 = location.hash.split('ai=')[1];
                                const uint8 = new Uint8Array(atob(b64).split('').map(c => c.charCodeAt(0)));
                                const json = new TextDecoder().decode(uint8);
                                const state = JSON.parse(json);
                                if (state.t && state.t.length > 0) {
                                    // Restore URLs for citation indexing (fragment is
                                    // attacker-controllable: sanitize every URL)
                                    if (state.u && Array.isArray(state.u)) {
                                        urls = state.u.map(safeCitationUrl);
                                    }
                                    
                                    conversation.turns = state.t.map(t => ({
                                        role: t.r === 'u' ? 'user' : 'assistant',
                                        content: t.c.trim(),
                                        ts: 0
                                    }));
                                    
                                    data.innerHTML = '';
                                    conversation.turns.forEach((turn, i) => {
                                        if (turn.role === 'user') {
                                            if (turn.content !== conversation.originalQuery) {
                                                const u = document.createElement('span');
                                                u.className = 'sxng-user-msg';
                                                u.textContent = turn.content;
                                                data.appendChild(u);
                                                const clr = document.createElement('div');
                                                clr.style.clear = 'both';
                                                data.appendChild(clr);
                                            }
                                        } else {
                                            data.appendChild(renderMarkdown(turn.content, urls));
                                        }
                                    });
                                    if(footer && is_interactive) footer.classList.add('sxng-ready');
                                    updateShowMore();
                                    restored = true;
                                }
                            } catch(e) { console.warn('Restore failed', e); }
                        }
                        document.getElementById('btn-copy').onclick = async (e) => {
                            const btn = e.currentTarget;
                            const originalContent = btn.innerHTML;
                            // Copy from conversation state (raw markdown), not the DOM,
                            // so reasoning boxes and UI text are never included.
                            const text = conversation.turns
                                .filter(t => t.role === 'assistant')
                                .map(t => t.content)
                                .join('\n\n');
                            await navigator.clipboard.writeText(text);
                            btn.innerHTML = '<svg viewBox="0 0 24 24" style="color:#a3be8c;"><path d="M9 16.17L4.83 12L3.41 13.41L9 19L21 7L19.59 5.59L9 16.17Z"/></svg>';
                            setTimeout(() => btn.innerHTML = originalContent, 2000);
                        };

                        document.getElementById('btn-regen').onclick = async () => {
                            data.innerHTML = '<span class="sxng-cursor"></span>';
                            footer.classList.remove('sxng-ready');
                            expandAnswer();
                            
                            if (conversation.turns.length > 0 && conversation.turns[conversation.turns.length - 1].role === 'assistant') {
                                conversation.turns.pop();
                            }
                            
                            updateState();
                            
                            if (conversation.turns.length <= 1) {
                                await startStream();
                            } else {
                                const val = conversation.turns[conversation.turns.length - 1].content;
                                const currentText = conversation.turns.slice(0, -1).slice(-6)
                                    .map(t => (t.role === 'user' ? 'Q' : 'A') + ': ' + t.content)
                                    .join('\\n\\n');
                                await startStream(val, currentText);
                            }
                            updateState();
                        };

                        const handleAction = async (e) => {
                            if (e) e.preventDefault();
                            const val = input.value.trim();
                            
                            conversation.turns.push({role: 'user', content: val, ts: Date.now()});
                            updateState();
                            
                            const currentText = conversation.turns.slice(0, -1).slice(-6)
                                .map(t => (t.role === 'user' ? 'Q' : 'A') + ': ' + t.content)
                                .join('\\n\\n');

                            input.value = '';
                            input.blur();
                            footer.classList.remove('sxng-ready');
                            expandAnswer();

                            if (val) {
                                const cursor = data.querySelector('.sxng-cursor');
                                if (cursor) cursor.remove();
                                const userMsg = document.createElement('span');
                                userMsg.className = 'sxng-user-msg';
                                userMsg.textContent = val;
                                data.appendChild(userMsg);
                                const clr = document.createElement('div');
                                clr.style.clear = 'both';
                                data.appendChild(clr);

                                const newCursor = document.createElement('span');
                                newCursor.className = 'sxng-cursor';
                                data.appendChild(newCursor);
                                
                                const synthesized = synthesizeQuery(q_init, val);
                                let auxContext = null;
                                try {
                                    const auxData = await fetch(script_root + '/ai-auxiliary-search', {
                                        method: 'POST',
                                        headers: {'Content-Type': 'application/json'},
                                        body: JSON.stringify({query: synthesized, lang: lang_init, offset: urls.length, tk: tk_init})
                                    }).then(r => r.json());
                                    if (auxData.context) {
                                        const originalBackground = conversation.originalContext.substring(0, 1500);
                                        auxContext = `FRESH SOURCES (most relevant):\\n${auxData.context}\\n\\nBACKGROUND (for reference):\\n${originalBackground}`;
                                        if (auxData.new_urls && Array.isArray(auxData.new_urls)) {
                                            urls = urls.concat(auxData.new_urls.map(safeCitationUrl));
                                        }
                                    }
                                } catch (err) {}
                                
                                await startStream(val, currentText, auxContext);
                                updateState();
                            } else {
                                const cursor = data.querySelector('.sxng-cursor');
                                if (cursor) cursor.remove();
                                data.appendChild(document.createElement('br'));
                                data.appendChild(document.createElement('br'));
                                const newCursor = document.createElement('span');
                                newCursor.className = 'sxng-cursor';
                                data.appendChild(newCursor);
                                await startStream("Continue", currentText);
                                updateState();
                            }
                        };

                        document.getElementById('sxng-action-form').onsubmit = handleAction;
                        input.onfocus = () => {
                            setTimeout(() => {
                                input.scrollIntoView({behavior: 'smooth', block: 'center'});
                            }, 300);
                        };


    function synthesizeQuery(original, followup) {
        const cleanOrig = original.replace(/^(what|how|why|when|where|who|which|is|are|can|does|do)(\s+(is|are|do|does|can|to|a|an|the))?\s+/i, '');
        const origWords = cleanOrig.split(' ').slice(0, 12);
        return `${origWords.join(' ')} ${followup}`.trim();
    }

    async function startStream(overrideQ = null, prevAnswer = null, auxContext = null) {
        if (isStreaming) {
            console.warn('[AI Answers] Stream already in progress, ignoring duplicate call');
            return;
        }
        
        isStreaming = true;
        box.classList.add('sxng-streaming');
        try {
            const ctx = auxContext || conversation.originalContext;

            const controller = new AbortController();
            let timeoutId = setTimeout(() => controller.abort(), 60000);
            const finalQ = overrideQ || q_init;
            
            const bodyObj = { q: finalQ, lang: lang_init, context: ctx, tk: tk_init, prev_answer: prevAnswer };
            const res = await fetch(script_root + '/ai-stream', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(bodyObj),
                signal: controller.signal
            });

            clearTimeout(timeoutId);
            if (!res.ok) {
                const errSpan = document.createElement('span');
                errSpan.style.color = '#bf616a';
                errSpan.textContent = "Error: " + res.statusText;
                data.appendChild(errSpan);
                return;
            }

            const reader = res.body.getReader();
            const decoder = new TextDecoder();
            let cursor = data.querySelector('.sxng-cursor');
            if (!cursor) {
                cursor = document.createElement('span');
                cursor.className = 'sxng-cursor';
                data.appendChild(cursor);
            }
            // Everything streamed this turn lands inside turnWrap (insertions
            // use cursor.before), so the finished turn can be re-rendered as
            // markdown without touching earlier turns.
            const turnWrap = document.createElement('span');
            turnWrap.className = 'sxng-turn';
            cursor.before(turnWrap);
            turnWrap.appendChild(cursor);

            let started = false;
            let collectedResponse = '';
            let isThinking = false, thoughtDiv = null;

            // Progressive markdown: blocks before the last blank line are final
            // (renderMarkdown treats a blank line as a hard block boundary), so
            // they render once into stableEl; the trailing partial block
            // re-renders wholesale into liveEl on each animation frame.
            // Incomplete inline tokens in the tail (e.g. `**bol`, `[1`) show as
            // literal text for a frame and self-correct on the next render.
            let stableEl = null, liveEl = null;
            let stableLen = 0;
            let renderQueued = false;

            const renderTick = () => {
                renderQueued = false;
                if (!liveEl) {
                    stableEl = document.createElement('span');
                    liveEl = document.createElement('span');
                    liveEl.className = 'sxng-chunk';
                    cursor.before(stableEl);
                    cursor.before(liveEl);
                }
                const boundary = collectedResponse.lastIndexOf('\n\n');
                if (boundary !== -1 && boundary + 2 > stableLen) {
                    const s = document.createElement('span');
                    s.className = 'sxng-chunk';
                    s.appendChild(renderMarkdown(collectedResponse.substring(stableLen, boundary), urls));
                    stableEl.appendChild(s);
                    stableLen = boundary + 2;
                }
                liveEl.textContent = '';
                liveEl.appendChild(renderMarkdown(collectedResponse.substring(stableLen), urls));
            };

            const scheduleRender = () => {
                if (renderQueued) return;
                renderQueued = true;
                if (window.requestAnimationFrame) requestAnimationFrame(renderTick);
                else renderTick();
            };

            let streamBuffer = '';
            while (true) {
                const {done, value} = await reader.read();
                if (done) break;

                clearTimeout(timeoutId);
                timeoutId = setTimeout(() => controller.abort(), 60000);

                const chunk = decoder.decode(value, {stream: true});
                if (!chunk) continue;
                
                streamBuffer += chunk;
                
                if (streamBuffer.match(/<\/?(?:t(?:h(?:i(?:n(?:k)?)?)?)?)?$/)) {
                    continue; 
                }

                while (true) {
                    const openIdx = streamBuffer.indexOf('<think>');
                    const closeIdx = streamBuffer.indexOf('</think>');
                    
                    if (openIdx === -1 && closeIdx === -1) break;

                    if (!isThinking) {
                        if (openIdx !== -1 && (closeIdx === -1 || openIdx < closeIdx)) {
                            const preTag = streamBuffer.substring(0, openIdx);
                            if (preTag) {
                                if (!started) {
                                    const trimmed = preTag.replace(/^[\s.,;:!?]+/, '');
                                    if (trimmed || collectedResponse.trim()) {
                                        if (cursor && !cursor.isConnected) data.appendChild(cursor);
                                        started = true;
                                    }
                                }
                                collectedResponse += preTag;
                                if (started) scheduleRender();
                            }
                            isThinking = true;
                            const details = document.createElement('details');
                            details.className = 'sxng-reasoning';
                            details.innerHTML = '<summary>Thought Process</summary>';
                            thoughtDiv = document.createElement('div');
                            thoughtDiv.className = 'sxng-thought-content';
                            details.appendChild(thoughtDiv);
                            (cursor ? cursor.before(details) : data.appendChild(details));
                            
                            streamBuffer = streamBuffer.substring(openIdx + 7);
                        } else {
                            streamBuffer = streamBuffer.replace('</think>', '');
                        }
                    } else {
                        if (closeIdx !== -1 && (openIdx === -1 || closeIdx < openIdx)) {
                            const thoughtText = streamBuffer.substring(0, closeIdx);
                            if (thoughtDiv) thoughtDiv.textContent += thoughtText;
                            isThinking = false;
                            streamBuffer = streamBuffer.substring(closeIdx + 8);
                        } else {
                            streamBuffer = streamBuffer.replace('<think>', '');
                        }
                    }
                }

                if (streamBuffer.length > 0) {
                    if (isThinking && thoughtDiv) {
                        thoughtDiv.textContent += streamBuffer;
                    } else {
                        if (!started) {
                            const trimmed = streamBuffer.replace(/^[\s.,;:!?]+/, '');
                            if (trimmed || collectedResponse.trim()) {
                                if (cursor && !cursor.isConnected) data.appendChild(cursor);
                                started = true;
                            }
                        }
                        collectedResponse += streamBuffer;
                        if (started) scheduleRender();
                    }
                    streamBuffer = '';
                }
            }
            
            if (streamBuffer.length > 0) {
                streamBuffer = streamBuffer.replace(/<\/?(?:t(?:h(?:i(?:n(?:k)?)?)?)?)?$/, '');
                if (streamBuffer.length > 0) {
                    if (isThinking && thoughtDiv) {
                        thoughtDiv.textContent += streamBuffer;
                    } else {
                        collectedResponse += streamBuffer;
                    }
                }
            }

            if (cursor) cursor.remove();

            if (!started && !collectedResponse.trim()) {
                const cursor = data.querySelector('.sxng-cursor');
                if (cursor) cursor.remove();
                
                const errSpan = document.createElement('span');
                if (thoughtDiv && thoughtDiv.textContent.trim().length > 0) {
                    errSpan.style.color = '#ebcb8b';
                    errSpan.textContent = 'Model provided reasoning but stopped before the final answer. Try adjusting token limits.';
                } else {
                    errSpan.style.color = '#bf616a';
                    errSpan.textContent = 'No response received. Check API configuration and server logs.';
                }
                data.appendChild(errSpan);
                return;
            }

            const finalText = collectedResponse.trim();
            if (finalText) {
                // Replace this turn's plain streamed chunks with the markdown
                // render, keeping the reasoning <details> box if present.
                Array.from(turnWrap.childNodes).forEach(n => {
                    const isReasoning = n.nodeType === 1 && n.classList && n.classList.contains('sxng-reasoning');
                    if (!isReasoning) n.remove();
                });
                turnWrap.appendChild(renderMarkdown(finalText, urls));
            }

            footer.classList.add('sxng-ready');

            if (collectedResponse) {
                conversation.turns.push({role: 'assistant', content: collectedResponse.trim(), ts: Date.now()});
            }
            
            // Save state if this was an initial generation or a regeneration
            if (arguments.length === 0 && typeof updateState === 'function') {
                updateState();
            }

        } catch (e) {
            console.error('[AI Answers] Fatal stream exception:', e);
            const errSpan = document.createElement('span');
            errSpan.style.cssText = 'color: #bf616a; font-weight: bold; display: block; margin-top: 0.5rem;';
            
            if (e.name === 'AbortError') {
                errSpan.textContent = "⚠️ Connection to AI provider timed out.";
            } else {
                errSpan.textContent = "⚠️ AI Widget encountered a fatal error. Check browser console.";
            }
            
            if (data) {
                const cursor = data.querySelector('.sxng-cursor');
                if (cursor) cursor.remove();
                data.appendChild(errSpan);
            }
        } finally {
            isStreaming = false;
            box.classList.remove('sxng-streaming');
            updateShowMore();
        }
    }

    if (!restored) startStream();
})();
