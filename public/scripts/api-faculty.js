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

  async function getAllEvents() {
    return await getJson('/api/faculty/all_events', { method: 'GET' });
  }

  async function getUpcomingEvents() {
    return await getJson('/api/faculty/events-dashboard', { method: 'GET' });
  }

  async function getPastEvents() {
    return await getJson('/api/faculty/events-past', { method: 'GET' });
  }

  async function getAllClubs() {
    return await getJson('/api/clubs/all_clubs', { method: 'GET' });
  }

  async function getClubsRoot() {
    const { ok, data } = await requestJson('/api/clubs/all_clubs', { method: 'GET' });
    if (!ok) throw new Error((data && (data.detail || data.message)) || 'Failed to load clubs');
    if (Array.isArray(data)) return data;
    if (data && Array.isArray(data.clubs)) return data.clubs;
    return [];
  }

  async function createEvent(eventData) {
    return await getJson('/api/events/create-event', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(eventData)
    });
  }

  async function filterParticipants(params) {
    const club = params && params.club ? params.club : null;
    const department = params && params.department ? params.department : null;
    const year = params && params.year ? params.year : null;

    let url = '/api/faculty/filter-participants?';
    if (club) url += `club=${encodeURIComponent(club)}&`;
    if (department) url += `department=${encodeURIComponent(department)}&`;
    if (year) url += `year=${encodeURIComponent(year)}&`;

    return await getJson(url, { method: 'GET' });
  }

  async function getDepartments() {
    return await getJson('/api/faculty/departments', { method: 'GET' });
  }

  async function getStudents() {
    const { ok, data } = await requestJson('/api/faculty/get-students', { method: 'GET' });
    if (!ok) throw new Error((data && (data.detail || data.message)) || 'Failed to load students');
    return data;
  }

  async function promoteAdmin(promotionData) {
    return await requestJson('/api/faculty/promote-admin', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(promotionData)
    });
  }

  async function getAdmins() {
    return await requestJson('/api/faculty/get-admins', { method: 'GET' });
  }

  async function removeAdmin(studentId, clubId) {
    return await requestJson('/api/faculty/remove-admin', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ studentId, clubId })
    });
  }

  async function getEventParticipants(eventId) {
    const url = `/api/faculty/event-participants?event_id=${encodeURIComponent(eventId)}`;
    return await getJson(url, { method: 'GET' });
  }

  window.FacultyAPI = {
    requestJson,
    getAllEvents,
    getUpcomingEvents,
    getPastEvents,
    getAllClubs,
    getClubsRoot,
    createEvent,
    filterParticipants,
    getDepartments,
    getStudents,
    promoteAdmin,
    getAdmins,
    removeAdmin,
    getEventParticipants
  };
})();
