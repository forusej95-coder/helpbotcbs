const chatArea = document.getElementById('chatArea');
const messageInput = document.getElementById('messageInput');
const sendBtn = document.getElementById('sendBtn');
const micBtn = document.getElementById('micBtn');
const clearBtn = document.getElementById('clearBtn');
const typingIndicator = document.getElementById('typingIndicator');
const charCount = document.getElementById('charCount');
const quickBtns = document.querySelectorAll('.quick-btn');
const audioPlayer = document.getElementById('audioPlayer');
const langSelectElement = document.getElementById('langSelect');

const BACKEND_URL = 'http://127.0.0.1:5002';
const CHAT_STORAGE_KEY = 'chatHistory';
const LANG_STORAGE_KEY = 'selectedLanguage';
const CONVERSATION_STORAGE_KEY = 'conversationId';

let conversationId = null;

// Voice state for Web Speech API
let isListening = false;
let recognition = null;

// Professional loading stages
let loadingStageTimer = null;
let loadingStageIndex = 0;

// TTS toggle state
let isSpeaking = false;
let activeTtsButton = null;

// Current selected language
let currentLang = 'en-IN';

// Track whether user is at bottom
let isUserAtBottom = true;

chatArea.addEventListener('scroll', () => {
  const threshold = 10;

  isUserAtBottom =
    chatArea.scrollHeight -
    chatArea.scrollTop -
    chatArea.clientHeight < threshold;
});

document.addEventListener('DOMContentLoaded', init);


// ============================================================
// INPUT WARNING
// ============================================================

function showInputWarning() {
  const warning = document.getElementById('inputWarning');

  if (!warning) {
    console.warn('inputWarning element not found');
    return;
  }

  warning.style.display = 'block';

  setTimeout(() => {
    warning.style.display = 'none';
  }, 2000);
}

// ============================================================
// LANGUAGE WARNING
// ============================================================

function showLanguageWarning() {
  const warning = document.createElement('div');

  warning.textContent =
    'Please ask your question in the selected language.';

  warning.style.position = 'fixed';
  warning.style.left = '50%';
  warning.style.bottom = '90px';
  warning.style.transform = 'translateX(-50%)';
  warning.style.background = '#ffffff';
  warning.style.color = '#333333';
  warning.style.padding = '10px 16px';
  warning.style.borderRadius = '8px';
  warning.style.boxShadow = '0 4px 15px rgba(0,0,0,0.2)';
  warning.style.border = '1px solid #ddd';
  warning.style.fontSize = '13px';
  warning.style.zIndex = '99999';
  warning.style.whiteSpace = 'nowrap';

  document.body.appendChild(warning);

  setTimeout(() => {
    warning.remove();
  }, 2000);
}


// ============================================================
// MARKDOWN → HTML
// ============================================================

function formatMarkdown(text) {

    if (!text) return '';

    const lines = text.split('\n');
    const output = [];

    for (let rawLine of lines) {

        let line = rawLine.trim();

        // --------------------------------------------------
        // Blank line
        // --------------------------------------------------
        if (!line) {
            output.push('');
            continue;
        }

        // --------------------------------------------------
        // NUMBERED STEPS
        // Never automatically bold numbered steps
        // --------------------------------------------------
        const numberedMatch = line.match(
            /^\*{0,2}(\d+)\.\s+([\s\S]*?)\*{0,2}$/
        );

        if (numberedMatch) {

            const number = numberedMatch[1];

            let stepText =
                numberedMatch[2].trim();

            // Remove accidental model bolding
            stepText = stepText.replace(
                /\*\*/g,
                ''
            );

            output.push(
                `${number}. ${stepText}`
            );

            // spacing after each step
            output.push('');

            continue;
        }

        // --------------------------------------------------
        // BULLETS
        // Never automatically bold bullets
        // --------------------------------------------------
        const bulletMatch = line.match(
            /^[•\-*]\s+(.+)$/
        );

        if (bulletMatch) {

            let bulletText =
                bulletMatch[1];

            bulletText = bulletText.replace(
                /\*\*/g,
                ''
            );

            output.push(
                `• ${bulletText}`
            );

            continue;
        }

        // --------------------------------------------------
        // Explicit Markdown bold
        // This works for EVERY language
        // --------------------------------------------------
        line = line.replace(
            /\*\*(.*?)\*\*/g,
            '<strong>$1</strong>'
        );

        // --------------------------------------------------
        // LANGUAGE-INDEPENDENT HEADING DETECTION
        // --------------------------------------------------

        const plainLine =
            line.replace(
                /<strong>|<\/strong>/g,
                ''
            ).trim();

        // Heading must:
        // - end with :
        // - be relatively short
        // - contain no sentence-ending punctuation
        // - not look like a normal sentence
        const headingMatch =
            plainLine.match(
                /^(.{1,60}):$/
            );

        if (headingMatch) {

            const heading =
                headingMatch[1].trim();

            // Avoid bolding long sentence-like text
            const wordCount =
                heading.split(/\s+/).length;

            const looksLikeSentence =
                wordCount > 8 ||
                /[.!?।॥]$/.test(heading);

            if (!looksLikeSentence) {

                output.push('');
                output.push(
                    `<strong>${heading}:</strong>`
                );
                output.push('');

                continue;
            }
        }

        // --------------------------------------------------
        // NORMAL TEXT
        // --------------------------------------------------
        output.push(line);
    }

    // ------------------------------------------------------
    // Convert spacing
    // ------------------------------------------------------

    let html = output.join('\n');

    // Maximum 1 empty paragraph between sections
    html = html.replace(
        /\n{3,}/g,
        '\n\n'
    );

    // Paragraph spacing
    html = html.replace(
        /\n\n/g,
        '<br><br>'
    );

    // Normal line breaks
    html = html.replace(
        /\n/g,
        '<br>'
    );

    // Remove excessive beginning/end breaks
    html = html.replace(
        /^(<br>)+/,
        ''
    );

    html = html.replace(
        /(<br>)+$/,
        ''
    );

    return html.trim();
}

// ============================================================
// LANGUAGE VALIDATOR
// ============================================================

// Kept for compatibility with your existing code.
// IMPORTANT:
// We no longer use this function to block user questions.
// The backend/LLM understands the user's actual language.
function isTextInSelectedLanguage(text, lang) {

  const patterns = {

    "en-IN":
      /^[A-Za-z0-9\s.,?!'"\-()]+$/,

    "hi-IN":
      /^[\u0900-\u097F0-9\s.,?!'"\-()]+$/,

    "mr-IN":
      /^[\u0900-\u097F0-9\s.,?!'"\-()]+$/,

    "ta-IN":
      /^[\u0B80-\u0BFF0-9\s.,?!'"\-()]+$/,

    "te-IN":
      /^[\u0C00-\u0C7F0-9\s.,?!'"\-()]+$/,

    "kn-IN":
      /^[\u0C80-\u0CFF0-9\s.,?!'"\-()]+$/,

    "bn-IN":
      /^[\u0980-\u09FF0-9\s.,?!'"\-()]+$/
  };

  if (!patterns[lang]) {
    return true;
  }

  return patterns[lang].test(text);
}


// ============================================================
// VOICE FUNCTIONS
// ============================================================

function applyCurrentLangToRecognition() {

  if (recognition) {
    recognition.lang = currentLang;
  }
}


// ============================================================
// SPEECH-TO-TEXT
// ============================================================

function initializeVoiceRecognition() {

  if ('webkitSpeechRecognition' in window) {

    recognition = new webkitSpeechRecognition();

    recognition.continuous = false;
    recognition.interimResults = false;

    // Use selected language for microphone recognition
    recognition.lang = currentLang;

    recognition.onstart = () => {

      isListening = true;

      showTyping(
        "Listening for your question..."
      );
    };


    recognition.onresult = (event) => {

      let transcript = '';

      for (
        let i = 0;
        i < event.results.length;
        i++
      ) {

        transcript +=
          event.results[i][0].transcript;
      }

      messageInput.value =
        transcript.trim();

      updateCharCount();
      autoResize();
    };


    recognition.onerror = (event) => {

      console.error(
        'Speech recognition error:',
        event.error
      );

      hideTyping();

      if (
        event.error !== 'no-speech' &&
        event.error !== 'aborted'
      ) {

        addMessage(
          `🎤 Voice Error: ${event.error}. Please ensure microphone access is granted.`,
          'bot'
        );
      }

      stopVoiceInput();
    };


    recognition.onend = () => {

      stopVoiceInput();

      const finalText =
        messageInput.value.trim();

      if (finalText.length > 0) {

        // Automatically send voice question
        sendMessage();
      }
    };


  } else {

    micBtn.style.display = 'none';

    console.warn(
      "Web Speech API not supported in this browser."
    );
  }
}


// ============================================================
// START VOICE
// ============================================================

function startVoiceInput() {

  if (!recognition) return;

  if (isListening) {

    recognition.stop();

    stopVoiceInput();

  } else {

    recognition.start();
  }
}


// ============================================================
// STOP VOICE
// ============================================================

function stopVoiceInput() {

  isListening = false;

  hideTyping();
}


// ============================================================
// TEXT-TO-SPEECH
// ============================================================
async function speakResponse(text, buttonElement) {

    if (!text || !text.trim()) {
        return;
    }

    if (isSpeaking) {
        audioPlayer.pause();
        audioPlayer.currentTime = 0;
        isSpeaking = false;

        if (activeTtsButton) {
            activeTtsButton.textContent = '🔊';
            activeTtsButton.title = 'Replay audio';
        }

        activeTtsButton = null;
        return;
    }

    isSpeaking = true;
    activeTtsButton = buttonElement;

    const originalText = buttonElement.textContent;
    const originalTitle = buttonElement.title;

    buttonElement.textContent = '⏹️';
    buttonElement.title = 'Stop audio';

    try {

        console.log("🔊 Requesting TTS...");
        console.log("Language:", currentLang);

        const response = await fetch(
            `${BACKEND_URL}/speak`,
            {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    text: text.trim(),
                    language: currentLang
                })
            }
        );

        if (!response.ok) {
            throw new Error(`TTS failed: HTTP ${response.status}`);
        }

        const result = await response.json();

        if (result.status !== 'success' || !result.audio) {
            throw new Error(
                result.message || 'No audio returned'
            );
        }

        console.log("✅ Audio received");

        const audioBytes = atob(result.audio);

        const uint8Array =
            new Uint8Array(audioBytes.length);

        for (let i = 0; i < audioBytes.length; i++) {
            uint8Array[i] =
                audioBytes.charCodeAt(i);
        }

        const audioBlob = new Blob(
            [uint8Array],
            { type: 'audio/mpeg' }
        );

        const audioUrl =
            URL.createObjectURL(audioBlob);

        audioPlayer.pause();
        audioPlayer.src = audioUrl;
        audioPlayer.volume = 1.0;

        // IMPORTANT:
        // Do not call load() or wait for canplay.
        // Start playback directly.
        const playPromise = audioPlayer.play();

        if (playPromise !== undefined) {
            await playPromise;
        }

        console.log("🔊 VOICE OUTPUT PLAYING");

        audioPlayer.onended = () => {

            URL.revokeObjectURL(audioUrl);

            isSpeaking = false;
            activeTtsButton = null;

            buttonElement.textContent =
                originalText;

            buttonElement.title =
                originalTitle;
        };

    } catch (error) {

    console.error("❌ TTS PLAYBACK ERROR");
    console.error("Name:", error.name);
    console.error("Message:", error.message);
    console.error("Code:", error.code);
    console.error("Full error:", error);

        isSpeaking = false;
        activeTtsButton = null;

        buttonElement.textContent =
            originalText;

        buttonElement.title =
            originalTitle;
    }
}


// ============================================================
// TTS CLEANUP
// ============================================================

function stopCurrentTts() {

    try {
        audioPlayer.pause();
        audioPlayer.currentTime = 0;
        audioPlayer.removeAttribute('src');
        audioPlayer.load();
    } catch (error) {
        console.warn("TTS stop error:", error);
    }

    if (activeTtsButton) {
        activeTtsButton.textContent = '🔊';
        activeTtsButton.title = 'Replay audio';
        activeTtsButton.disabled = false;
    }

    activeTtsButton = null;
    isSpeaking = false;
}

function cleanupTts(
  button,
  originalText,
  originalTitle,
  audioUrl = null
) {

  if (audioUrl) {
    URL.revokeObjectURL(audioUrl);
  }

  isSpeaking = false;

  activeTtsButton = null;

  button.textContent =
    originalText;

  button.title =
    originalTitle;

  button.disabled = false;

  audioPlayer.onended = null;
}


// ============================================================
// CONVERSATION INITIALIZATION
// ============================================================

async function initializeConversation() {

  try {

    const result =
      await chrome.storage.local.get(
        [CONVERSATION_STORAGE_KEY]
      );


    // Existing conversation
    if (
      result[CONVERSATION_STORAGE_KEY]
    ) {

      conversationId =
        result[CONVERSATION_STORAGE_KEY];

      console.log(
        'Existing conversation:',
        conversationId
      );

      return;
    }


    // Create new backend conversation
    const response =
      await fetch(
        `${BACKEND_URL}/new_conversation`,
        {
          method: 'POST'
        }
      );


    if (!response.ok) {

      throw new Error(
        `Conversation creation failed: ${response.status}`
      );
    }


    const data =
      await response.json();


    if (!data.conversation_id) {

      throw new Error(
        'Backend did not return conversation_id.'
      );
    }


    conversationId =
      data.conversation_id;


    await chrome.storage.local.set({

      [CONVERSATION_STORAGE_KEY]:
        conversationId

    });


    console.log(
      'New conversation created:',
      conversationId
    );


  } catch (error) {

    console.error(
      'Conversation initialization failed:',
      error
    );

    // Backend can create one automatically
    // if conversation_id is missing.
    conversationId = null;
  }
}


// ============================================================
// INIT
// ============================================================

async function init() {

  const langSelect =
    document.getElementById('langSelect');


  if (langSelect) {

    // Restore last selected language
    chrome.storage.local.get(
      [LANG_STORAGE_KEY],
      (result) => {

        if (
          result[LANG_STORAGE_KEY]
        ) {

          currentLang =
            result[LANG_STORAGE_KEY];

          langSelect.value =
            currentLang;

        } else {

          currentLang =
            langSelect.value;
        }

        applyCurrentLangToRecognition();
      }
    );


    // Save language on change
    langSelect.addEventListener(
      'change',
      () => {

        currentLang =
          langSelect.value;

        chrome.storage.local.set({

          [LANG_STORAGE_KEY]:
            currentLang

        });

        applyCurrentLangToRecognition();
      }
    );
  }


  initializeVoiceRecognition();


  sendBtn.addEventListener(
    'click',
    sendMessage
  );


  messageInput.addEventListener(
    'keypress',
    handleKeyPress
  );


  messageInput.addEventListener(
    'input',
    updateCharCount
  );


  clearBtn.addEventListener(
    'click',
    clearChat
  );


  micBtn.addEventListener(
    'click',
    startVoiceInput
  );


  chatArea.addEventListener(
    'click',
    (e) => {

      const btn =
        e.target.closest('.quick-btn');

      if (!btn) return;

      const question =
        btn.getAttribute(
          'data-question'
        );

      if (!question) return;

      messageInput.value =
        question;

      sendMessage();
    }
  );


  messageInput.addEventListener(
    'input',
    autoResize
  );


  // Initialize backend conversation
  // BEFORE loading/sending messages.
  await initializeConversation();

  await loadChat();
}


// ============================================================
// SEND MESSAGE
// ============================================================

async function sendMessage() {

  const message =
    messageInput.value.trim();


  // Empty input
  if (message === '') {

    showInputWarning();

    messageInput.focus();

    return;
  }
// Language validation
if (!isTextInSelectedLanguage(message, currentLang)) {

  showLanguageWarning();

  messageInput.focus();

  return;
}

  // Display user message
  await addMessage(
    message,
    'user'
  );

  scrollToBottom(true);


  // Clear input
  messageInput.value = '';

  updateCharCount();

  autoResize();


  // Loading
  showProfessionalLoading();


  try {

    const response =
      await fetch(
        `${BACKEND_URL}/ask_question`,
        {
          method: 'POST',

          headers: {
            'Content-Type':
              'application/json'
          },

          body: JSON.stringify({

            question: message,

            conversation_id:
              conversationId,

            lang: currentLang

          })
        }
      );


    const result =
      await response.json();


    hideTyping();


    if (response.ok) {

      // Backend returns `sources`
      await addMessage(
        result.answer,
        'bot',
        {
          references:
            result.sources || []
        }
      );


      // Synchronize conversation ID
      if (
        result.conversation_id
      ) {

        conversationId =
          result.conversation_id;


        await chrome.storage.local.set({

          [CONVERSATION_STORAGE_KEY]:
            conversationId

        });
      }


      scrollToBottom(true);


    } else {

      addMessage(

        `🤖 AI Error: ${
          result.message ||
          result.error ||
          'Unknown server error.'
        }`,

        'bot'
      );
    }


  } catch (error) {

    hideTyping();


    addMessage(
      `❌ Connection Error: Failed to get response from server.`,
      'bot'
    );


    console.error(error);
  }
}


// ============================================================
// ADD MESSAGE
// ============================================================

async function addMessage(
  text,
  type,
  meta = {}
) {

  const result =
    await chrome.storage.local.get(
      [CHAT_STORAGE_KEY]
    );


  const history =
    result[CHAT_STORAGE_KEY] || [];


  if (
    history.length === 0 &&
    chatArea.querySelector(
      '.welcome-card'
    )
  ) {

    chatArea.innerHTML = '';
  }


  renderMessage(
    text,
    type,
    meta
  );


  history.push({
    text,
    type,
    meta
  });


  await saveChat(history);
}


// ============================================================
// LOAD CHAT
// ============================================================

async function loadChat() {

  const result =
    await chrome.storage.local.get(
      [CHAT_STORAGE_KEY]
    );


  const history =
    result[CHAT_STORAGE_KEY] || [];


  chatArea.innerHTML = '';


  if (history.length === 0) {

    chatArea.innerHTML = `

      <div class="welcome-card">

        <div class="welcome-icon">
          🏦
        </div>

        <h3>
          Welcome to Trust Fintech Q&A!
        </h3>

        <p>
          Your AI assistant is ready.
          Ask questions based on the
          approved Trust Bank banking
          manual using text or voice (🎤).
        </p>

      </div>

    `;

  } else {

    history.forEach(
      item => {

        renderMessage(
          item.text,
          item.type,
          item.meta
        );
      }
    );
  }


  scrollToBottom();
}


// ============================================================
// SAVE CHAT
// ============================================================

async function saveChat(history) {

  await chrome.storage.local.set({

    [CHAT_STORAGE_KEY]:
      history

  });
}


// ============================================================
// RENDER MESSAGE
// ============================================================

function renderMessage(
  text,
  type,
  meta = {}
) {

  const messageDiv =
    document.createElement('div');


  messageDiv.className =
    `chat-bubble ${type}-bubble`;


  const formatted =
    formatMarkdown(text);


  // ========================================================
  // DOCUMENT REFERENCES
  // ========================================================

  let sourceHtml = "";


  if (
    meta.references &&
    Array.isArray(meta.references) &&
    meta.references.length > 0
  ) {

    sourceHtml = `

      <div class="ref-mini-box">

        <div class="ref-title">
          📚 References
        </div>

        ${
          meta.references
            .map(ref => {

              // New backend:
              // { filename, file_id }

              // Old frontend:
              // { pdf, page, section }

              let file =
                ref.filename ||
                ref.pdf ||
                "";


              if (
                file.includes("aHR0") ||
                file.length > 200
              ) {

                file = "";
              }


              if (
                file.includes(".pdf")
              ) {

                file =
                  file.split("/").pop();
              }


              // Do NOT invent page numbers.
              const page =
                ref.page || null;


              if (
                !file &&
                !page &&
                !ref.section
              ) {

                return "";
              }


              return `

                <div class="ref-line">

                  •
                  <span class="ref-file">
                    ${file}
                  </span>

                  ${
                    ref.section
                      ? `
                        <span class="ref-page">
                          • ${ref.section}
                        </span>
                      `
                      : ""
                  }

                  ${
                    page
                      ? `
                        <span class="ref-page">
                          • Page ${page}
                        </span>
                      `
                      : ""
                  }

                </div>

              `;

            })
            .join("")
        }

      </div>

    `;
  }


  else if (meta.source) {

    sourceHtml =
      `<span class="source">📚 ${meta.source}</span>`;
  }


  // ========================================================
  // BOT MESSAGE
  // ========================================================

  if (type === "bot") {

    messageDiv.innerHTML = `

      <div class="message-content">
        ${formatted}
      </div>

      <div class="citations">
        ${sourceHtml}
      </div>

      <div class="message-meta">

        <span class="time">
          ${getCurrentTime()}
        </span>

      </div>

    `;


    // Replay button
    const replayBtn =
      document.createElement(
        "button"
      );


    replayBtn.className =
      "icon-btn";


    replayBtn.textContent =
      "🔊";


    replayBtn.title =
      "Replay audio";


    replayBtn.onclick =
      () => speakResponse(
        text,
        replayBtn
      );


    const metaDiv =
      messageDiv.querySelector(
        ".message-meta"
      );


    if (metaDiv) {

      metaDiv.prepend(
        replayBtn
      );
    }


  } else {

    // User message

    messageDiv.innerHTML = `

      <div class="message-content">
        ${formatted}
      </div>

      <div class="message-meta">

        <span class="time">
          ${getCurrentTime()}
        </span>

      </div>

    `;
  }


  chatArea.appendChild(
    messageDiv
  );


  scrollToBottom();


  // Animation
  messageDiv.style.opacity = "0";

  messageDiv.style.transform =
    "translateY(10px)";


  setTimeout(() => {

    messageDiv.style.transition =
      "all 0.3s ease";

    messageDiv.style.opacity = "1";

    messageDiv.style.transform =
      "translateY(0)";

  }, 10);
}


// ============================================================
// PROFESSIONAL LOADING
// ============================================================

function showProfessionalLoading() {

  const stages = [

    "Processing request…",

    "Searching relevant documents…",

    "Generating response…"

  ];


  let index = 0;


  if (loadingStageTimer) {

    clearInterval(
      loadingStageTimer
    );

    loadingStageTimer = null;
  }


  showTyping(
    stages[index]
  );


  loadingStageTimer =
    setInterval(() => {

      index++;


      if (
        index < stages.length
      ) {

        showTyping(
          stages[index]
        );

      } else {

        showTyping(
          "Still processing — thank you for your patience"
        );


        clearInterval(
          loadingStageTimer
        );

        loadingStageTimer = null;
      }

    }, 3000);
}


// ============================================================
// TYPING INDICATOR
// ============================================================

function showTyping(customText) {

  const typingText =
    document.querySelector(
      '.typing-text'
    );


  typingText.textContent =
    customText;


  typingIndicator.style.display =
    'flex';
}


// ============================================================
// HIDE TYPING
// ============================================================

function hideTyping() {

  if (loadingStageTimer) {

    clearInterval(
      loadingStageTimer
    );

    loadingStageTimer = null;
  }


  if (!isListening) {

    typingIndicator.style.display =
      'none';
  }
}


// ============================================================
// KEYBOARD
// ============================================================

function handleKeyPress(e) {

  if (
    e.key === 'Enter' &&
    !e.shiftKey
  ) {

    e.preventDefault();

    sendMessage();
  }
}


// ============================================================
// CHARACTER COUNT
// ============================================================

function updateCharCount() {

  const length =
    messageInput.value.length;


  charCount.textContent =
    `${length} / 500`;


  charCount.style.color =
    length > 450
      ? '#ff4444'
      : '#7ba5b8';
}


// ============================================================
// AUTO RESIZE
// ============================================================

function autoResize() {

  messageInput.style.height =
    'auto';


  messageInput.style.height =
    Math.min(
      messageInput.scrollHeight,
      100
    ) + 'px';
}


// ============================================================
// SCROLL
// ============================================================

function scrollToBottom() {

  const messages =
    chatArea.querySelectorAll(
      ".chat-bubble"
    );


  const last =
    messages[messages.length - 1];


  if (!last) return;


  requestAnimationFrame(() => {

    last.scrollIntoView({

      behavior: "auto",

      block: "start"

    });

  });
}


// ============================================================
// TIME
// ============================================================

function getCurrentTime() {

  const now =
    new Date();


  return now.toLocaleTimeString(
    'en-IN',
    {
      hour: '2-digit',
      minute: '2-digit'
    }
  );
}


// ============================================================
// STATUS BAR
// ============================================================

function updateStatusBar(status) {

  const statusBar =
    document.querySelector(
      '.status-text'
    );


  if (statusBar) {

    statusBar.textContent =
      `• Happy to Help `;
  }
}


// ============================================================
// CLEAR CHAT + RESET BACKEND MEMORY
// ============================================================

async function clearChat() {

  if (
    !confirm(
      'Clear all messages?'
    )
  ) {

    return;
  }


  try {

    // Delete old backend conversation
    if (conversationId) {

      try {

        await fetch(
          `${BACKEND_URL}/conversation/${conversationId}`,
          {
            method: 'DELETE'
          }
        );

      } catch (error) {

        console.warn(
          'Old backend conversation could not be deleted:',
          error
        );
      }
    }


    // Create new backend conversation
    const response =
      await fetch(
        `${BACKEND_URL}/new_conversation`,
        {
          method: 'POST'
        }
      );


    if (!response.ok) {

      throw new Error(
        `New conversation failed: ${response.status}`
      );
    }


    const data =
      await response.json();


    if (!data.conversation_id) {

      throw new Error(
        'Backend did not return a new conversation_id.'
      );
    }


    conversationId =
      data.conversation_id;


    await chrome.storage.local.set({

      [CONVERSATION_STORAGE_KEY]:
        conversationId,

      [CHAT_STORAGE_KEY]:
        []

    });


    await loadChat();


  } catch (error) {

    console.error(
      'Failed to clear conversation:',
      error
    );


    conversationId = null;


    await chrome.storage.local.set({

      [CHAT_STORAGE_KEY]:
        []

    });


    await loadChat();
  }
}


// ============================================================
// STOP TTS WHEN POPUP LOSES FOCUS
// ============================================================



// ============================================================
// FORCE STOP TTS
// ============================================================

function forceStopTts() {

  try {

    if (audioPlayer) {

      audioPlayer.pause();

      audioPlayer.currentTime = 0;

      audioPlayer.src = "";
    }

  } catch (e) {

    console.warn(
      "Audio cleanup error",
      e
    );
  }


  isSpeaking = false;


  if (activeTtsButton) {

    activeTtsButton.textContent =
      "🔊";

    activeTtsButton.title =
      "Replay audio";

    activeTtsButton.disabled =
      false;

    activeTtsButton = null;
  }


  if (audioPlayer) {

    audioPlayer.onended = null;
  }
}


// ============================================================
// GLOBAL TTS STOP BUTTON
// ============================================================

const globalTtsStopBtn =
  document.getElementById(
    'globalTtsStop'
  );


if (globalTtsStopBtn) {

  globalTtsStopBtn.addEventListener(
    'click',
    stopAllTtsCompletely
  );
}


// ============================================================
// STOP ALL TTS
// ============================================================

function stopAllTtsCompletely() {

  try {

    if (audioPlayer) {

      audioPlayer.pause();

      audioPlayer.currentTime = 0;

      audioPlayer.src = '';

      audioPlayer.onended = null;
    }

  } catch (e) {

    console.warn(
      'TTS stop error:',
      e
    );
  }


  // Reset speaking state
  isSpeaking = false;


  // Reset active button
  if (activeTtsButton) {

    activeTtsButton.textContent =
      '🔊';

    activeTtsButton.title =
      'Replay audio';

    activeTtsButton.disabled =
      false;

    activeTtsButton = null;
  }
}