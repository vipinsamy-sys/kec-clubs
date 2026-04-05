(function () {
	'use strict';

	const CommonUI = (window.CommonUI = window.CommonUI || {});

	function resolveScope(scope) {
		if (!scope) return document;
		if (scope instanceof Element || scope === document) return scope;
		if (typeof scope === 'string') return document.querySelector(scope);
		return document;
	}

	function toText(value) {
		if (value === null || value === undefined) return '0';
		return String(value);
	}

	function countFrom(data, preferredArrayKey) {
		if (!data) return 0;
		if (typeof data.count === 'number') return data.count;
		if (Array.isArray(data)) return data.length;

		if (preferredArrayKey && Array.isArray(data[preferredArrayKey])) {
			return data[preferredArrayKey].length;
		}

		const fallbackArray =
			(Array.isArray(data.events) && data.events) ||
			(Array.isArray(data.students) && data.students) ||
			(Array.isArray(data.participants) && data.participants) ||
			null;

		if (fallbackArray) return fallbackArray.length;
		return 0;
	}

	function setText(scope, selector, value) {
		const root = resolveScope(scope);
		if (!root || !selector) return false;

		const el = root.querySelector(selector);
		if (!el) return false;

		el.textContent = toText(value);
		return true;
	}

	function setStat(scope, id, value) {
		if (!id) return false;
		const safeId = typeof CSS !== 'undefined' && CSS.escape ? CSS.escape(id) : id;
		return setText(scope, `#${safeId}`, value);
	}

    //event participants related functions

	function escapeHtml(unsafe) {
		if (unsafe === null || unsafe === undefined) return '';
		return String(unsafe)
			.replaceAll('&', '&amp;')
			.replaceAll('<', '&lt;')
			.replaceAll('>', '&gt;')
			.replaceAll('"', '&quot;')
			.replaceAll("'", '&#039;');
	}

	function getParticipantsApi() {
		if (window.FacultyAPI && typeof window.FacultyAPI.getEventParticipants === 'function') {
			return window.FacultyAPI;
		}
		if (window.StudentAPI && typeof window.StudentAPI.getEventParticipants === 'function') {
			return window.StudentAPI;
		}
		return null;
	}

	async function fallbackCoordinatorParticipants(eventId) {
		const response = await fetch(
			`/api/users/coordinator/participants?event_id=${encodeURIComponent(eventId)}`,
			{ method: 'GET', credentials: 'include' }
		);
		let data = {};
		try {
			data = await response.json();
		} catch (_) {
			data = {};
		}
		if (!response.ok) {
			const err = new Error(data.detail || data.message || `Request failed (${response.status})`);
			err.status = response.status;
			throw err;
		}
		return data;
	}

	function setEventSelectOptions(events, options) {
		const opts = options || {};
		const selectId = opts.eventSelectId || 'event-select';
		const placeholder = opts.placeholder || 'Choose an event...';
		const select = document.getElementById(selectId);
		if (!select) return;

		let html = `<option value="">${placeholder}</option>`;
		(events || []).forEach((event) => {
			const id = event && (event._id || event.event_id || event.id);
			if (!id) return;
			const title = (event.title || event.name || 'Event').toString();
			html += `<option value="${String(id)}">${escapeHtml(title)}</option>`;
		});
		select.innerHTML = html;
	}

	function loadEventParticipants(options) {
		const opts = options || {};
		const eventSelectId = opts.eventSelectId || 'event-select';
		const participantsListId = opts.participantsListId || 'participants-list';
		const select = document.getElementById(eventSelectId);
		const container = document.getElementById(participantsListId);

		if (!container) return;

		const eventId = select ? select.value : null;
		if (!eventId) {
			container.innerHTML = '<p class="text-muted text-center"><i class="fas fa-info-circle me-2"></i>Select an event to view participants</p>';
			return;
		}

		container.innerHTML = '<div class="text-center"><div class="spinner-border text-warning" role="status"><span class="visually-hidden">Loading...</span></div></div>';

		const api = getParticipantsApi();
		const request = api
			? api.getEventParticipants(eventId)
			: fallbackCoordinatorParticipants(eventId);

		request
			.then((data) => {
				const participants = (data && Array.isArray(data.participants)) ? data.participants : [];
				if (!participants.length) {
					container.innerHTML = '<p class="text-muted text-center">No participants for this event</p>';
					return;
				}

				let html = `
					<div class="table-responsive">
						<table class="table table-dark table-hover table-striped mb-0">
							<thead class="table-light">
								<tr>
									<th>Name</th>
									<th>Email</th>
									<th>Roll Number</th>
									<th>Department</th>
									<th>Year</th>
									<th>Club</th>
								</tr>
							</thead>
							<tbody>
				`;

				participants.forEach((p) => {
					html += `
						<tr>
							<td>${escapeHtml(p.name || '-')}</td>
							<td>${escapeHtml(p.email || '-')}</td>
							<td>${escapeHtml(p.user_roll || p.roll_number || '-')}</td>
							<td>${escapeHtml(p.department || '-')}</td>
							<td>${escapeHtml(p.year || '-')}</td>
							<td>${escapeHtml(p.club || '-')}</td>
						</tr>
					`;
				});

				html += `
							</tbody>
						</table>
					</div>
					<div class="mt-2 text-muted small">Total: ${participants.length} participant(s)</div>
				`;

				container.innerHTML = html;
			})
			.catch((error) => {
				console.error('Error loading participants:', error);
				let msg = 'Failed to load participants';
				if (error && error.status === 401) msg = 'Please login again to view participants';
				else if (error && error.status === 403) msg = 'Coordinator access required for this event';
				else if (error && error.message) msg = error.message;
				container.innerHTML = `<p class="text-danger text-center">${escapeHtml(msg)}</p>`;
			});
	}

	function exportParticipantsCSV(options) {
		const opts = options || {};
		const participantsListId = opts.participantsListId || 'participants-list';
		const filterOutputId = opts.filterOutputId || 'filter-output';

		const participantsContainer = document.getElementById(participantsListId);
		const filterContainer = document.getElementById(filterOutputId);

		let table = null;
		let eventTitle = 'participants';

		if (participantsContainer) {
			table = participantsContainer.querySelector('table');
			const titleEl = participantsContainer.querySelector('h6');
			if (titleEl) {
				eventTitle = titleEl.textContent.trim().replace(/^Event:\s*/i, '').replace(/[^a-z0-9]/gi, '_');
			}
		}

		if (!table && filterContainer) {
			table = filterContainer.querySelector('table');
			if (!table) {
				const tables = filterContainer.querySelectorAll('table');
				if (tables.length > 0) table = tables[0];
			}
		}

		if (!table) {
			alert('No participants to export. Please select an event or apply filters first.');
			return;
		}

		let csv = '';
		const rows = table.querySelectorAll('tr');
		if (!rows.length) {
			alert('No data found in table. Please ensure participants are loaded.');
			return;
		}

		rows.forEach((row) => {
			const cells = row.querySelectorAll('td, th');
			const rowData = Array.from(cells)
				.map((cell) => `"${cell.textContent.trim().replace(/"/g, '""')}"`)
				.join(',');
			if (rowData.trim()) csv += `${rowData}\n`;
		});

		if (!csv.trim()) {
			alert('No data to export.');
			return;
		}

		const filename = `${eventTitle}_participants_${new Date().getTime()}.csv`;
		const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
		const link = document.createElement('a');
		const url = URL.createObjectURL(blob);
		link.setAttribute('href', url);
		link.setAttribute('download', filename);
		link.style.visibility = 'hidden';
		document.body.appendChild(link);
		link.click();
		document.body.removeChild(link);
		setTimeout(() => URL.revokeObjectURL(url), 100);
	}

	CommonUI.resolveScope = resolveScope;
	CommonUI.countFrom = countFrom;
	CommonUI.setText = setText;
	CommonUI.setStat = setStat;
	CommonUI.setEventSelectOptions = setEventSelectOptions;
	CommonUI.loadEventParticipants = loadEventParticipants;
	CommonUI.exportParticipantsCSV = exportParticipantsCSV;
})();

