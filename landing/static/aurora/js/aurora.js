// =========================================================
// NAVBAR: cambia a sólida al hacer scroll
// =========================================================
const afNavbar = document.getElementById('afNavbar');
function afHandleNavbarScroll(){
  if (window.scrollY > 40){ afNavbar.classList.add('is-scrolled'); }
  else { afNavbar.classList.remove('is-scrolled'); }
}
afHandleNavbarScroll();
window.addEventListener('scroll', afHandleNavbarScroll);

// Cierra el menú colapsado en móvil al elegir un enlace
document.querySelectorAll('.af-nav-link, .af-nav-cta').forEach(function(link){
  link.addEventListener('click', function(){
    const collapseEl = document.getElementById('afNavCollapse');
    if (collapseEl.classList.contains('show')) {
      bootstrap.Collapse.getOrCreateInstance(collapseEl).hide();
    }
  });
});

// =========================================================
// CONTADORES ANIMADOS (se activan al entrar en pantalla)
// =========================================================
const afCounters = document.querySelectorAll('.af-counter');
let afCountersStarted = false;

function afAnimateCounters(){
  if (afCountersStarted) return;
  afCountersStarted = true;
  afCounters.forEach(function(counter){
    const target = parseInt(counter.getAttribute('data-target'), 10);
    const duration = 1400;
    const start = performance.now();

    function step(now){
      const progress = Math.min((now - start) / duration, 1);
      const value = Math.floor(progress * target);
      counter.textContent = value.toLocaleString('es-CO');
      if (progress < 1){ requestAnimationFrame(step); }
      else { counter.textContent = target.toLocaleString('es-CO'); }
    }
    requestAnimationFrame(step);
  });
}

const afTrustSection = document.querySelector('.af-trust');
if ('IntersectionObserver' in window && afTrustSection){
  const afObserver = new IntersectionObserver(function(entries){
    entries.forEach(function(entry){
      if (entry.isIntersecting){ afAnimateCounters(); }
    });
  }, { threshold: 0.4 });
  afObserver.observe(afTrustSection);
} else {
  afAnimateCounters();
}

// =========================================================
// AÑO ACTUAL EN EL FOOTER
// =========================================================
document.getElementById('afYear').textContent = new Date().getFullYear();

// =========================================================
// WIDGET CHATBOT "AURORITA"  (conectado a n8n vía proxy Django)
// =========================================================
const afBotToggle  = document.getElementById('afBotToggle');
const afBotWindow  = document.getElementById('afBotWindow');
const afBotClose   = document.getElementById('afBotClose');
const afBotForm    = document.getElementById('afBotForm');
const afBotInput   = document.getElementById('afBotInput');
const afBotMessages= document.getElementById('afBotMessages');
const afBotAttach  = document.getElementById('afBotAttach');
const afBotFile    = document.getElementById('afBotFile');
const afBotMic     = document.getElementById('afBotMic');
const afBotGeo     = document.getElementById('afBotGeo');
const afBotMenuToggle = document.getElementById('afBotMenuToggle');
const afBotMenu       = document.getElementById('afBotMenu');

// --- Configuración del proxy (definida como data-* en el <form> de base.html) ---
const AF_CHAT_URL  = afBotForm.dataset.chatUrl;
const AF_RESET_URL = afBotForm.dataset.resetUrl;
const AF_CSRF      = afBotForm.dataset.csrf;

// Mensaje de bienvenida original; se restaura al iniciar cada conversación nueva.
const AF_WELCOME_HTML = afBotMessages.innerHTML;

// El chat_id lo administra Django desde la sesión; el JS no lo envía.

// Convierte un Blob/File a base64 SIN el prefijo "data:...;base64,"
function afToBase64(blob){
  return new Promise(function(resolve, reject){
    const reader = new FileReader();
    reader.onloadend = function(){
      const result = String(reader.result || '');
      const comma = result.indexOf(',');
      resolve(comma >= 0 ? result.slice(comma + 1) : result);
    };
    reader.onerror = reject;
    reader.readAsDataURL(blob);
  });
}

// Detiene cualquier proceso en curso (grabación, menú, flujos) sin tocar la conversación.
function afCleanupState(){
  if (afRecording) afStopRecording();
  afCloseMenu();
  afDocStep  = null;
  afLocating = false;
}

// Deja la ventana en su estado inicial: solo el mensaje de bienvenida.
function afResetUI(){
  afCleanupState();
  afBotMessages.innerHTML = AF_WELCOME_HTML;
  afSetBusy(false);
}

// Pide al backend una conversación nueva (descarta el chat_id de la sesión).
function afResetServerConversation(){
  if (!AF_RESET_URL) return;
  fetch(AF_RESET_URL, {
    method: 'POST',
    headers: { 'X-CSRFToken': AF_CSRF },
    credentials: 'same-origin',
    keepalive: true
  }).catch(function(){ /* silencioso: es solo un reinicio */ });
}

function afOpenBot(){
  afResetUI();                       // cada apertura arranca una conversación desde cero
  afBotWindow.classList.add('is-open');
  afBotWindow.setAttribute('aria-hidden', 'false');
  afBotToggle.classList.add('is-open');
  afBotToggle.setAttribute('aria-expanded', 'true');
  afBotToggle.style.opacity = '0';
  afBotToggle.style.transform = 'scale(0.5)';
  afBotToggle.style.pointerEvents = 'none';
  afBotInput.focus();
}
function afCloseBot(){
  afCleanupState();
  afResetServerConversation();       // renueva el chat_id para la próxima apertura
  afBotWindow.classList.remove('is-open');
  afBotWindow.setAttribute('aria-hidden', 'true');
  afBotToggle.classList.remove('is-open');
  afBotToggle.setAttribute('aria-expanded', 'false');
  afBotToggle.style.opacity = '';
  afBotToggle.style.transform = '';
  afBotToggle.style.pointerEvents = '';
  afBotToggle.focus();
}
afBotToggle.addEventListener('click', function(){
  afBotWindow.classList.contains('is-open') ? afCloseBot() : afOpenBot();
});
afBotClose.addEventListener('click', afCloseBot);

// Cierra el menú (o, si no hay menú abierto, el chat) con la tecla Escape
document.addEventListener('keydown', function(e){
  if (e.key !== 'Escape') return;
  if (afBotMenu.classList.contains('is-open')){ afCloseMenu(); return; }
  if (afBotWindow.classList.contains('is-open')){ afCloseBot(); }
});

function afScrollBottom(){
  afBotMessages.scrollTop = afBotMessages.scrollHeight;
}

// Escapa HTML para que el contenido del bot nunca inyecte etiquetas.
function afEscapeHtml(s){
  return String(s)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

// Formato en línea sobre texto YA escapado. Soporta:
//   [texto](url)  -> botón/enlace clickeable (abre en pestaña nueva)
//   url suelta     -> se auto-enlaza
//   **negrita**    -> <strong>
// Los enlaces se extraen a marcadores antes de aplicar negrita para no romper
// las etiquetas <a>. Solo se aceptan URLs http(s).
function afInlineMarkdown(s){
  const links = [];
  const stash = function(url, label){
    // La URL viene escapada (& -> &amp;), que es valido dentro de href.
    const i = links.length;
    links.push({ url: url, label: label || url });
    // Marcador seguro (el texto ya viene escapado, '@' no lo produce el escape).
    return '@@AFLINK' + i + '@@';
  };

  // 1) Enlaces Markdown [texto](url)
  s = s.replace(/\[([^\]]+)\]\((https?:\/\/[^)\s]+)\)/g, function(_, label, url){
    return stash(url, label);
  });
  // 2) URLs sueltas fuera de un enlace Markdown
  s = s.replace(/(^|[\s(])(https?:\/\/[^\s<]+)/g, function(m, pre, url){
    return pre + stash(url, null);
  });
  // 3) Negrita
  s = s.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
  // 4) Restaurar enlaces como <a>. Los que van a la pasarela (/pago/) como boton.
  return s.replace(/@@AFLINK(\d+)@@/g, function(_, idx){
    const l = links[+idx];
    const esPago = /\/pago\/?\?/.test(l.url);
    const cls = esPago ? 'af-bot-link af-bot-link-btn' : 'af-bot-link';
    const label = esPago
      ? '<i class="bi bi-shield-lock-fill"></i> ' + l.label
      : l.label;
    return '<a class="' + cls + '" href="' + l.url +
           '" target="_blank" rel="noopener noreferrer">' + label + '</a>';
  });
}

// Convierte un subconjunto seguro de Markdown a HTML: negrita, listas (- / *)
// y saltos de línea. Escapa el HTML primero; solo emite etiquetas propias.
function afRenderRich(text){
  const lines = afEscapeHtml(String(text).replace(/\r\n/g, '\n')).split('\n');
  let html = '';
  let inList = false;
  lines.forEach(function(raw){
    const line = raw.trim();
    const item = line.match(/^[-*]\s+(.*)$/);
    if (item){
      if (!inList){ html += '<ul class="af-bot-list">'; inList = true; }
      html += '<li>' + afInlineMarkdown(item[1]) + '</li>';
      return;
    }
    if (inList){ html += '</ul>'; inList = false; }
    if (line !== '') html += '<div>' + afInlineMarkdown(line) + '</div>';
  });
  if (inList) html += '</ul>';
  return html;
}

// Sonido de notificación (dos notas cortas) cuando el bot responde.
// Se sintetiza con Web Audio: no requiere archivo externo. El AudioContext se
// crea perezosamente tras el primer gesto del usuario (enviar un mensaje), así
// que las políticas de autoplay del navegador no lo bloquean.
let afAudioCtx = null;
function afPlayNotify(){
  try{
    const AC = window.AudioContext || window.webkitAudioContext;
    if (!AC) return;
    if (!afAudioCtx) afAudioCtx = new AC();
    if (afAudioCtx.state === 'suspended') afAudioCtx.resume();
    const ctx = afAudioCtx;
    const now = ctx.currentTime;
    const gain = ctx.createGain();
    gain.connect(ctx.destination);
    gain.gain.setValueAtTime(0.0001, now);
    gain.gain.exponentialRampToValueAtTime(0.15, now + 0.02);
    gain.gain.exponentialRampToValueAtTime(0.0001, now + 0.35);
    [[880, now], [1174.66, now + 0.12]].forEach(function(pair){
      const osc = ctx.createOscillator();
      osc.type = 'sine';
      osc.frequency.setValueAtTime(pair[0], pair[1]);
      osc.connect(gain);
      osc.start(pair[1]);
      osc.stop(pair[1] + 0.18);
    });
  }catch(e){ /* silencioso: el sonido es un extra, nunca debe romper el chat */ }
}

function afAddMessage(text, sender){
  const bubble = document.createElement('div');
  const isUser = sender === 'user';
  bubble.className = 'af-bot-msg ' + (isUser ? 'af-bot-msg-user' : 'af-bot-msg-bot');
  // Los mensajes del usuario van como texto plano; los del bot con formato enriquecido.
  if (isUser){ bubble.textContent = text; }
  else       { bubble.innerHTML = afRenderRich(text); }
  afBotMessages.appendChild(bubble);
  afScrollBottom();
  if (!isUser) afPlayNotify();   // avisa al usuario que llegó respuesta del bot
  return bubble;
}

// Muestra una miniatura de la imagen subida como burbuja del usuario
function afAddImageMessage(file){
  const bubble = document.createElement('div');
  bubble.className = 'af-bot-msg af-bot-msg-user af-bot-msg-img';
  const img = document.createElement('img');
  img.src = URL.createObjectURL(file);
  img.alt = 'Documento de identidad';
  img.onload = function(){ URL.revokeObjectURL(img.src); afScrollBottom(); };
  bubble.appendChild(img);
  afBotMessages.appendChild(bubble);
  afScrollBottom();
}

// Indicador "escribiendo…" (se crea y se retira)
function afShowTyping(){
  const el = document.createElement('div');
  el.className = 'af-bot-msg af-bot-msg-bot af-bot-typing';
  el.id = 'afBotTyping';
  el.innerHTML = '<span></span><span></span><span></span>';
  afBotMessages.appendChild(el);
  afScrollBottom();
  return el;
}
function afHideTyping(){
  const el = document.getElementById('afBotTyping');
  if (el) el.remove();
}

// Muestra un reproductor con la nota de voz grabada como burbuja del usuario
function afAddAudioMessage(blob){
  const bubble = document.createElement('div');
  bubble.className = 'af-bot-msg af-bot-msg-user af-bot-msg-audio';
  const audio = document.createElement('audio');
  audio.controls = true;
  audio.preload = 'metadata';
  audio.src = URL.createObjectURL(blob);
  bubble.appendChild(audio);
  afBotMessages.appendChild(bubble);
  afScrollBottom();
}

// Muestra la ubicación compartida como burbuja del usuario (enlace a Google Maps)
function afAddLocationMessage(lat, lng){
  const bubble = document.createElement('div');
  bubble.className = 'af-bot-msg af-bot-msg-user af-bot-msg-geo';
  const link = document.createElement('a');
  link.href = 'https://www.google.com/maps?q=' + lat + ',' + lng;
  link.target = '_blank';
  link.rel = 'noopener noreferrer';
  link.innerHTML = '<i class="bi bi-geo-alt-fill"></i>'
    + '<span>Mi ubicación<small>' + lat.toFixed(5) + ', ' + lng.toFixed(5) + '</small></span>';
  bubble.appendChild(link);
  afBotMessages.appendChild(bubble);
  afScrollBottom();
}

// Bloquea/desbloquea la barra de entrada mientras se espera a n8n
function afSetBusy(busy){
  afBotInput.disabled     = busy;
  afBotAttach.disabled    = busy;
  afBotMic.disabled       = busy;
  afBotGeo.disabled       = busy;
  afBotMenuToggle.disabled= busy;
  afBotForm.querySelector('.af-bot-send').disabled = busy;
}

// =========================================================
// MENÚ DESPLEGABLE DE ADJUNTOS (documento / ubicación / audio)
// =========================================================
function afOpenMenu(){
  afBotMenu.classList.add('is-open');
  afBotMenu.setAttribute('aria-hidden', 'false');
  afBotMenuToggle.classList.add('is-active');
  afBotMenuToggle.setAttribute('aria-expanded', 'true');
}
function afCloseMenu(){
  afBotMenu.classList.remove('is-open');
  afBotMenu.setAttribute('aria-hidden', 'true');
  afBotMenuToggle.classList.remove('is-active');
  afBotMenuToggle.setAttribute('aria-expanded', 'false');
}
function afMenuIsOpen(){ return afBotMenu.classList.contains('is-open'); }

// El botón principal abre/cierra el menú… salvo cuando hay una grabación en
// curso: entonces actúa como botón "detener y enviar".
afBotMenuToggle.addEventListener('click', function(e){
  e.stopPropagation();
  if (afRecording){ afStopRecording(); return; }
  afMenuIsOpen() ? afCloseMenu() : afOpenMenu();
});

// Cierra el menú al elegir cualquier opción
[afBotAttach, afBotGeo, afBotMic].forEach(function(item){
  item.addEventListener('click', afCloseMenu);
});

// Cierra el menú al hacer clic fuera de él
document.addEventListener('click', function(e){
  if (afMenuIsOpen() && !afBotMenu.contains(e.target) && !afBotMenuToggle.contains(e.target)){
    afCloseMenu();
  }
});

// =========================================================
// LLAMADAS AL PROXY (Django -> n8n)
// =========================================================
// POST JSON al proxy y devuelve el texto de respuesta (siempre {respuesta}).
async function afPostJson(payload){
  const res = await fetch(AF_CHAT_URL, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'X-CSRFToken': AF_CSRF },
    credentials: 'same-origin',   // envía la cookie de sesión (Django pone el chat_id)
    body: JSON.stringify(payload)
  });
  const data = await res.json().catch(function(){ return {}; });
  return data.respuesta || 'No recibí respuesta. Intenta de nuevo.';
}

async function afSendText(text){
  afSetBusy(true);
  afShowTyping();
  try {
    const respuesta = await afPostJson({ mensaje: text });
    afHideTyping();
    afAddMessage(respuesta, 'bot');
  } catch (err) {
    afHideTyping();
    afAddMessage('Ups, no pude conectarme en este momento. Inténtalo de nuevo en unos segundos. 🙏', 'bot');
  } finally {
    afSetBusy(false);
    afBotInput.focus();
  }
}

async function afSendDocument(file){
  afSetBusy(true);
  afShowTyping();
  try {
    const imagen = await afToBase64(file);
    const formato = (file.type || 'image/jpeg').toLowerCase();
    const respuesta = await afPostJson({ imagen: imagen, formato: formato });
    afHideTyping();
    afAddMessage(respuesta, 'bot');
    return true;
  } catch (err) {
    afHideTyping();
    afAddMessage('No pude subir la imagen. Revisa tu conexión e inténtalo de nuevo. 🙏', 'bot');
    return false;
  } finally {
    afSetBusy(false);
  }
}

async function afSendAudio(blob){
  afSetBusy(true);
  afShowTyping();
  try {
    const audio = await afToBase64(blob);
    const respuesta = await afPostJson({ audio: audio });
    afHideTyping();
    afAddMessage(respuesta, 'bot');
  } catch (err) {
    afHideTyping();
    afAddMessage('No pude enviar el audio. Revisa tu conexión e inténtalo de nuevo. 🙏', 'bot');
  } finally {
    afSetBusy(false);
  }
}

async function afSendLocation(lat, lng){
  afSetBusy(true);
  afShowTyping();
  try {
    // La ubicación se envía como texto para que n8n la procese por el flujo normal.
    const mensaje = 'Ubicación compartida: latitud ' + lat + ', longitud ' + lng;
    const respuesta = await afPostJson({ mensaje: mensaje });
    afHideTyping();
    afAddMessage(respuesta, 'bot');
  } catch (err) {
    afHideTyping();
    afAddMessage('No pude enviar tu ubicación. Revisa tu conexión e inténtalo de nuevo. 🙏', 'bot');
  } finally {
    afSetBusy(false);
    afBotInput.focus();
  }
}

// =========================================================
// COMPARTIR UBICACIÓN (Geolocation API del navegador)
// =========================================================
let afLocating = false;

function afShareLocation(){
  if (afLocating) return;
  if (!('geolocation' in navigator)){
    afAddMessage('Tu navegador no permite compartir la ubicación. Puedes escribir tu ciudad o municipio. 🙏', 'bot');
    return;
  }
  afLocating = true;
  afSetBusy(true);
  afShowTyping();                       // feedback mientras se resuelve el GPS
  navigator.geolocation.getCurrentPosition(
    function(pos){
      afLocating = false;
      afHideTyping();
      afSetBusy(false);
      const lat = pos.coords.latitude;
      const lng = pos.coords.longitude;
      afAddLocationMessage(lat, lng);
      afSendLocation(lat, lng);
    },
    function(err){
      afLocating = false;
      afHideTyping();
      afSetBusy(false);
      const msg = (err && err.code === err.PERMISSION_DENIED)
        ? 'No autorizaste el acceso a tu ubicación. Puedes escribir tu ciudad o municipio. 📍'
        : 'No pude obtener tu ubicación. Inténtalo de nuevo o escribe tu ciudad o municipio. 🙏';
      afAddMessage(msg, 'bot');
    },
    { enableHighAccuracy: true, timeout: 10000, maximumAge: 0 }
  );
}

afBotGeo.addEventListener('click', function(){
  if (afBotGeo.disabled) return;
  afShareLocation();
});

// =========================================================
// GRABACIÓN DE NOTAS DE VOZ (MediaRecorder)
// =========================================================
let afMediaRecorder = null;
let afAudioChunks   = [];
let afRecording     = false;

// Elige el primer formato de audio soportado por el navegador
function afPickAudioMime(){
  const candidates = [
    'audio/webm;codecs=opus', 'audio/webm',
    'audio/ogg;codecs=opus',  'audio/ogg',
    'audio/mp4'
  ];
  if (window.MediaRecorder && MediaRecorder.isTypeSupported){
    for (let i = 0; i < candidates.length; i++){
      if (MediaRecorder.isTypeSupported(candidates[i])) return candidates[i];
    }
  }
  return '';
}

// Mientras se graba, el botón principal del menú se convierte en "detener".
function afSetMicRecording(on){
  afRecording = on;
  if (on) afCloseMenu();
  const label = on ? 'Detener y enviar grabación' : 'Enviar documento, ubicación o audio';
  afBotMenuToggle.classList.toggle('is-recording', on);
  afBotMenuToggle.setAttribute('aria-label', label);
  afBotMenuToggle.setAttribute('data-tooltip', label);
  afBotMenuToggle.innerHTML = on ? '<i class="bi bi-stop-fill"></i>' : '<i class="bi bi-list"></i>';
}

async function afStartRecording(){
  if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia || !window.MediaRecorder){
    afAddMessage('Tu navegador no permite grabar audio. Prueba con una versión reciente de Chrome, Edge o Firefox. 🙏', 'bot');
    return;
  }
  let stream;
  try {
    stream = await navigator.mediaDevices.getUserMedia({ audio: true });
  } catch (err) {
    afAddMessage('No pude acceder al micrófono. Revisa los permisos del navegador y vuelve a intentarlo. 🎤', 'bot');
    return;
  }

  const mime = afPickAudioMime();
  afMediaRecorder = mime ? new MediaRecorder(stream, { mimeType: mime }) : new MediaRecorder(stream);
  afAudioChunks = [];

  afMediaRecorder.addEventListener('dataavailable', function(e){
    if (e.data && e.data.size > 0) afAudioChunks.push(e.data);
  });
  afMediaRecorder.addEventListener('stop', function(){
    stream.getTracks().forEach(function(t){ t.stop(); });   // libera el micrófono
    const type = afMediaRecorder.mimeType || mime || 'audio/webm';
    const blob = new Blob(afAudioChunks, { type: type });
    afAudioChunks = [];
    if (blob.size > 0){
      afAddAudioMessage(blob);
      afSendAudio(blob);
    }
  });

  afMediaRecorder.start();
  afSetMicRecording(true);
}

function afStopRecording(){
  if (afMediaRecorder && afRecording){
    afSetMicRecording(false);
    try { afMediaRecorder.stop(); } catch (e) { /* ignorar */ }
  }
}

afBotMic.addEventListener('click', function(){
  if (afRecording) return;   // la grabación se detiene desde el botón principal del menú
  afStartRecording();
});

// =========================================================
// FLUJO GUIADO DE DOCUMENTO DE IDENTIDAD (frente -> reverso)
// =========================================================
// afDocStep: null (inactivo) | 'frente' | 'reverso'
let afDocStep = null;

function afStartDocFlow(){
  if (afDocStep) return;          // ya hay un flujo en curso
  afDocStep = 'frente';
  afAddMessage('📄 Vamos a validar tu documento de identidad. Por favor sube una foto del FRENTE (cara con tu foto). Toca el clip para seleccionarla.', 'bot');
  afBotFile.click();
}

afBotAttach.addEventListener('click', function(){
  if (afDocStep){
    afBotFile.click();            // reanuda el paso pendiente
  } else {
    afStartDocFlow();
  }
});

afBotFile.addEventListener('change', async function(){
  const file = afBotFile.files && afBotFile.files[0];
  afBotFile.value = '';           // permite re-seleccionar el mismo archivo
  if (!file) return;

  // Si el usuario adjunta sin haber iniciado el flujo, asumimos que es el frente
  if (!afDocStep) afDocStep = 'frente';

  const ladoActual = afDocStep;
  afAddImageMessage(file);
  const ok = await afSendDocument(file);   // el contrato es {imagen, formato}; el lado se guía por el chat
  if (!ok){
    // Mantener el paso para reintentar
    afAddMessage('Vuelve a tocar el clip 📎 para reintentar la foto del ' + ladoActual + '.', 'bot');
    return;
  }

  if (ladoActual === 'frente'){
    afDocStep = 'reverso';
    afAddMessage('¡Perfecto! ✅ Ahora sube una foto del REVERSO de tu documento.', 'bot');
    afBotFile.click();
  } else {
    afDocStep = null;             // flujo completo
    afAddMessage('¡Listo! 🎉 Recibí ambas caras de tu documento. Estoy validando la información…', 'bot');
  }
});

// =========================================================
// ENVÍO DE MENSAJES DE TEXTO
// =========================================================
afBotForm.addEventListener('submit', function(e){
  e.preventDefault();
  const text = afBotInput.value.trim();
  if (!text) return;
  afAddMessage(text, 'user');
  afBotInput.value = '';
  afSendText(text);
});
