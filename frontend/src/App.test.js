import React, { act } from 'react';
import { createRoot } from 'react-dom/client';
import App from './App';

describe('Gemini configuration in the rendered dashboard', () => {
  let container;
  let root;
  let originalFetch;
  let originalBackendUrl;

  beforeEach(() => {
    originalFetch = global.fetch;
    originalBackendUrl = process.env.REACT_APP_BACKEND_URL;
    process.env.REACT_APP_BACKEND_URL = 'http://synthetic.invalid';
    global.IS_REACT_ACT_ENVIRONMENT = true;
    jest.useFakeTimers();
    container = document.createElement('div');
    document.body.appendChild(container);
    root = createRoot(container);
  });

  afterEach(async () => {
    await act(async () => root.unmount());
    container.remove();
    jest.useRealTimers();
    global.fetch = originalFetch;
    if (originalBackendUrl === undefined) delete process.env.REACT_APP_BACKEND_URL;
    else process.env.REACT_APP_BACKEND_URL = originalBackendUrl;
    delete global.IS_REACT_ACT_ENVIRONMENT;
  });

  test.each([
    ['paused', 'PAUSED'],
    ['configured_unverified', 'CONFIGURED · UNVERIFIED'],
    ['unavailable', 'NOT CONFIGURED'],
    [undefined, 'UNKNOWN'],
  ])('renders %s from HTTP health metadata without claiming online', async (status, expected) => {
    const health = { services: { gemini: 'available', openai: 'available', anthropic: 'unavailable' } };
    if (status !== undefined) health.provider_configuration = { gemini: { status, live_api_verification: 'NOT_RUN' } };
    global.fetch = jest.fn(async url => ({
      ok: true,
      json: async () => url.endsWith('/api/health') ? health : url.endsWith('/api/analytics') ? {} : [],
    }));
    await act(async () => root.render(<App />));
    const geminiName = Array.from(container.querySelectorAll('span')).find(el => el.textContent === 'Google Gemini');
    expect(geminiName.parentElement.textContent).toContain(expected);
    expect(geminiName.parentElement.textContent).not.toContain('ONLINE');
    expect(global.fetch).toHaveBeenCalledWith('http://synthetic.invalid/api/health');
    const openaiName = Array.from(container.querySelectorAll('span')).find(el => el.textContent === 'OpenAI GPT');
    expect(openaiName.parentElement.textContent).toContain('ONLINE');
  });
});
