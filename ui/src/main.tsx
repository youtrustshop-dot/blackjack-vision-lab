import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';
import SimulatorWindow from './SimulatorWindow';
import './style.css';
import './dark.css';
ReactDOM.createRoot(document.getElementById('root')!).render(<React.StrictMode>{new URLSearchParams(location.search).has('simulator')?<SimulatorWindow/>:<App/>}</React.StrictMode>);
