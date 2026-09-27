import React from 'react';
import ReactDOM from 'react-dom/client';
// CSS is bundled by the frontend build tool and has no TypeScript declarations.
// @ts-ignore
import './index.css';

import App from './App';
import reportWebVitals from './reportWebVitals';

const root = ReactDOM.createRoot(
  document.getElementById('root') as HTMLElement
);

root.render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);

reportWebVitals();