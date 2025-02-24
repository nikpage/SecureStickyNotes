const CryptoJS = require('crypto-js');
const { ipcRenderer } = require('electron');

const SECRET_KEY = 'your-secret-key'; // Replace with a secure key

function encrypt(text) {
  return CryptoJS.AES.encrypt(text, SECRET_KEY).toString();
}

function decrypt(ciphertext) {
  const bytes = CryptoJS.AES.decrypt(ciphertext, SECRET_KEY);
  return bytes.toString(CryptoJS.enc.Utf8);
}

function clearBuffer(buffer) {
  buffer.fill(0);
}

document.getElementById('note-editor').addEventListener('input', (e) => {
  const plaintext = e.target.value;
  const encrypted = encrypt(plaintext);
  ipcRenderer.send('save-note', encrypted);
  clearBuffer(Buffer.from(plaintext)); // Clear plaintext from memory
});

ipcRenderer.on('load-note', (_, encrypted) => {
  const plaintext = decrypt(encrypted);
  document.getElementById('note-editor').value = plaintext;
  clearBuffer(Buffer.from(plaintext)); // Clear plaintext from memory
});
