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

// --- Configuración del proxy (definida como data-* en el <form> de base.html) ---
const AF_CHAT_URL = afBotForm.dataset.chatUrl;
const AF_CSRF     = afBotForm.dataset.csrf;

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

function afOpenBot(){
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

// Cierra el chat con la tecla Escape
document.addEventListener('keydown', function(e){
  if (e.key === 'Escape' && afBotWindow.classList.contains('is-open')){
    afCloseBot();
  }
});

function afScrollBottom(){
  afBotMessages.scrollTop = afBotMessages.scrollHeight;
}

function afAddMessage(text, sender){
  const bubble = document.createElement('div');
  bubble.className = 'af-bot-msg ' + (sender === 'user' ? 'af-bot-msg-user' : 'af-bot-msg-bot');
  bubble.textContent = text;
  afBotMessages.appendChild(bubble);
  afScrollBottom();
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

// Bloquea/desbloquea la barra de entrada mientras se espera a n8n
function afSetBusy(busy){
  afBotInput.disabled  = busy;
  afBotAttach.disabled = busy;
  afBotMic.disabled    = busy;
  afBotForm.querySelector('.af-bot-send').disabled = busy;
}

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

function afSetMicRecording(on){
  afRecording = on;
  afBotMic.classList.toggle('is-recording', on);
  afBotMic.setAttribute('aria-label', on ? 'Detener y enviar grabación' : 'Grabar mensaje de voz');
  afBotMic.innerHTML = on ? '<i class="bi bi-stop-fill"></i>' : '<i class="bi bi-mic-fill"></i>';
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
  if (afRecording) afStopRecording();
  else             afStartRecording();
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
