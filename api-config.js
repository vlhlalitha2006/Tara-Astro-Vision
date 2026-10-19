(() => {
  const productionApiBase = '';
  const configuredApiBase = (window.TAV_API_BASE || productionApiBase).trim();

  if (configuredApiBase) {
    window.TAV_API_BASE = configuredApiBase.replace(/\/+$/, '');
    return;
  }

  const { hostname, port, protocol } = window.location;
  const isLocalhost = hostname === 'localhost' || hostname === '127.0.0.1';
  if (protocol === 'file:' || (isLocalhost && port && port !== '8000')) {
    window.TAV_API_BASE = 'http://localhost:8000';
    return;
  }

  window.TAV_API_BASE = '';
})();
