// Share and check tab, reveal window 

function tweakSpecialHtml(text) {
    return String(text)
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#039;');
}

function formatNumber(number) {
    return number.toLocaleString('en-US');
}


function formatShort(number) {
    if (number >= 1000000000) {
        return Math.round(number / 100000000) / 10 + 'B';
    } else if (number >= 1000000) {
        return Math.round(number / 100000) / 10 + 'M';
    } else if (number >= 1000) {
        return Math.round(number / 1000) + 'K';
    } else {
        return String(number);
    }
}


function showMessage(messageBox, text, type) {
    messageBox.textContent = text;
    messageBox.className = 'message ' + type;
    messageBox.hidden = false;
}

async function askServer(url, method, body) {
    const options = { method: method };

    if (body) {
        options.headers = { 'Content-Type': 'application/json' };
        options.body = JSON.stringify(body);
    }

    let response;
    try {
        response = await fetch(url, options);
    } catch (error) {
        throw new Error('Could not reach the server. Check your internet connection.');
    }

    let data;
    try {
        data = await response.json();
    } catch (error) {
        throw new Error('The server had a problem. Please try again.');
    }

    if (!response.ok) {
        throw new Error(data.error);
    }

    return data;
}


async function copyText(text, copyBtn, textInput) {
    try {
        await navigator.clipboard.writeText(text);
        copyBtn.textContent = 'Copied!';
    } catch (error) {
        if (textInput) {
            textInput.select();
            copyBtn.textContent = 'Press Ctrl+C';
        } else {
            copyBtn.textContent = 'Copy failed';
        }
    }

    setTimeout(function () {
        copyBtn.textContent = 'Copy';
    }, 2000);
}



const pages = document.querySelectorAll('.page');
const tabBtns = document.querySelectorAll('.tab');

function showTab(pageName) {
    for (let i = 0; i < pages.length; i += 1) {
        pages[i].hidden = pages[i].id !== pageName;
    }

    for (let i = 0; i < tabBtns.length; i += 1) {
        const tabName = tabBtns[i].getAttribute('data-tab');
        tabBtns[i].classList.toggle('active', tabName === pageName);
    }
}

function clickTab(event) {
    showTab(event.currentTarget.getAttribute('data-tab'));
}

for (let i = 0; i < tabBtns.length; i += 1) {
    tabBtns[i].addEventListener('click', clickTab);
}


const shareForm = document.getElementById('shareForm');
const secretTxt = document.getElementById('secret-txt');
const secretCount = document.getElementById('secret-count');
const ttlSelect = document.getElementById('ttl-select');
const minutesBox = document.getElementById('minutes-box');
const customMin = document.getElementById('custom-min');
const shareBtn = document.getElementById('share-btn');
const shareBtnTxt = document.getElementById('share-btn-txt');
const shareMsg = document.getElementById('share-msg');
const linkBox = document.getElementById('link-box');
const linkInput = document.getElementById('link-input');
const linkBtn = document.getElementById('link-btn');
const deleteBtn = document.getElementById('delete-btn');


let lastMetadataKey = '';


function updateCounter() {
    secretCount.textContent = secretTxt.value.length + ' / 500';
}


function typingSecret() {
    updateCounter();

    clearTimeout(leakTimer);
    leakTimer = setTimeout(checkLeak, 600);
}


function changeExpiry() {
    minutesBox.hidden = ttlSelect.value !== 'custom';
}

function getExpirySeconds() {
    if (ttlSelect.value !== 'custom') {
        return Number(ttlSelect.value);
    }

    const minutes = Number(customMin.value);

    if (!Number.isInteger(minutes) || minutes < 1 || minutes > 10080) {
        return 0;
    }

    return minutes * 60;
}

async function createLink(event) {
    event.preventDefault();

    const secret = secretTxt.value.trim();
    const expirySeconds = getExpirySeconds();

    if (secret === '') {
        showMessage(shareMsg, 'Plzz type something to share.', 'error');
        return;
    }

    if (expirySeconds === 0) {
        showMessage(shareMsg, 'Custom time must be a whole number of minutes', 'error');
        return;
    }

    shareBtn.disabled = true;
    shareBtnTxt.textContent = 'Creating...';
    shareMsg.hidden = true;

    try {
        const data = await askServer('/api/share', 'POST', { secret: secret, ttl: expirySeconds });

        lastMetadataKey = data.metadata_key;
        linkInput.value = window.location.origin + '/secret/' + data.secret_key;
        linkBox.hidden = false;

        // clear the box so the secret is not left on the page
        secretTxt.value = '';
        updateCounter();
        leakNote.hidden = true;
    } catch (error) {
        showMessage(shareMsg, error.message, 'error');
    }

    shareBtn.disabled = false;
    shareBtnTxt.textContent = 'Create one-time link';
}

function copyLink() {
    copyText(linkInput.value, linkBtn, linkInput);
}

// deletes the secret before opened
async function deleteLink() {
    if (lastMetadataKey === '') return;

    try {
        await askServer('/api/burn/' + lastMetadataKey, 'POST');
        linkBox.hidden = true;
        lastMetadataKey = '';
        showMessage(shareMsg, 'Link deleted. Nobody can open it now.', '');
    } catch (error) {
        showMessage(shareMsg, error.message, 'error');
    }
}

secretTxt.addEventListener('input', typingSecret);
ttlSelect.addEventListener('change', changeExpiry);
shareForm.addEventListener('submit', createLink);
linkBtn.addEventListener('click', copyLink);
deleteBtn.addEventListener('click', deleteLink);


// ===== checking leaks ====

const leakNote = document.getElementById('leak-note');
let leakTimer = null;

// turns the password into a SHA-1 hashing 
async function makeHash(text) {
    const textBytes = new TextEncoder().encode(text);
    const hashBuffer = await crypto.subtle.digest('SHA-1', textBytes);
    const hashBytes = new Uint8Array(hashBuffer);
    let hashTxt = '';

    for (let i = 0; i < hashBytes.length; i += 1) {
        hashTxt += hashBytes[i].toString(16).padStart(2, '0');
    }

    return hashTxt.toUpperCase();
}


function passwordStrength(password) {
    let points = 0;

    if (password.length >= 8) points += 1;
    if (password.length >= 12) points += 1;
    if (/[a-z]/.test(password) && /[A-Z]/.test(password)) points += 1;
    if (/[0-9]/.test(password)) points += 1;
    if (/[^A-Za-z0-9]/.test(password)) points += 1;

    if (points <= 2) {
        return 'Weak';
    } else if (points === 3) {
        return 'Medium';
    } else {
        return 'Strong';
    }
}

function showLeakNote(text, type) {
    leakNote.textContent = text;
    leakNote.className = 'leak-note ' + type;
    leakNote.hidden = false;
}

// asks api if this password leaked, but only sends 5 characters of the hash
async function checkLeak() {
    const password = secretTxt.value;

    if (password === '' || password.length > 100) {
        leakNote.hidden = true;
        return;
    }

    
    if (!window.crypto || !crypto.subtle) {
        showLeakNote('Leak check needs a secure (https) connection.', 'checking');
        return;
    }

    showLeakNote('Checking if this password leaked...', 'checking');

    try {
        const hash = await makeHash(password);
        const firstPart = hash.slice(0, 5);
        const restPart = hash.slice(5);
        const data = await askServer('/api/password/' + firstPart, 'GET');
        const strength = passwordStrength(password);

        let leakCount = 0;
        if (data.results[restPart]) {
            leakCount = data.results[restPart];
        }

        if (secretTxt.value !== password) return;

        if (leakCount > 0) {
            showLeakNote('⚠ This password was found ' + formatNumber(leakCount) +
                ' times in leaked password lists. Strength: ' + strength +
                '. Consider making a new one.', 'leaked');
        } else {
            showLeakNote('✓ Not found in any breach. Strength: ' + strength + '.', 'safe');
        }
    } catch (error) {
        showLeakNote('cannot check for leaks but you can still create the link.', 'checking');
    }
}


// Reveal page

const cover = document.getElementById('cover');
const coverTitle = document.getElementById('cover-title');
const coverTxt = document.getElementById('cover-txt');
const secretText = document.getElementById('secret-text');
const copySecretBtn = document.getElementById('copySecretButton');

async function revealSecret() {
    if (cover.classList.contains('used')) return;

    const secretKey = window.location.pathname.split('/')[2];

    cover.disabled = true;
    coverTitle.textContent = 'Opening...';

    try {
        const data = await askServer('/api/reveal/' + secretKey, 'POST');
        secretText.textContent = data.value;
        cover.classList.add('open');
    } catch (error) {
        cover.classList.add('used');
        coverTitle.textContent = 'Cannot open this secret';
        coverTxt.textContent = error.message;
    }
}

function copySecret() {
    copyText(secretText.textContent, copySecretBtn, null);
}

cover.addEventListener('click', revealSecret);
copySecretBtn.addEventListener('click', copySecret);


// ===== Start =====

function startApp() {
    if (window.location.pathname.startsWith('/secret/')) {
        document.getElementById('tabs').hidden = true;
        showTab('reveal');
        return;
    }

    loadBreaches();

    if (window.location.hash === '#share') {
        showTab('share');
    }
}

startApp();

