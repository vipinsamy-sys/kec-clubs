/* Backend communication layer for student/admin dashboards.
   Contains ONLY API calls + request/response parsing.
   UI rendering stays in the HTML files.
*/

(function () {
  'use strict';

  async function getJson(url, options) {
    const response = await fetch(url, options);
    return await response.json();
  }

  async function safeJson(response) {
    try {
      return await response.json();
    } catch (e) {
      return { message: 'Invalid server response' };
    }
  }

  async function requestJson(url, options) {
    const response = await fetch(url, options);
    const data = await safeJson(response);
    const ok = response.ok && !(data && data.message === 'Invalid server response');
    return { ok, status: response.status, data, response };
  }

  async function getUpcomingEvents() {
    return await getJson('/api/users/events-dashboard', { method: 'GET' });
  }

  async function getAllEvents() {
    return await getJson('/api/users/all_events', { method: 'GET' });
  }

  async function getPastEvents() {
    return await getJson('/api/users/events-past', { method: 'GET' });
  }

  async function registerForEvent(userId, eventId) {
    return await requestJson('/api/users/register-event', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        user_id: userId,
        event_id: eventId
      })
    });
  }

  window.StudentAPI = {
    requestJson,
    getUpcomingEvents,
    getAllEvents,
    getPastEvents,
    registerForEvent
  };
})();
