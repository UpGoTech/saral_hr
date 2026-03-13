frappe.pages["attendance-dashboard"].on_page_load = function (wrapper) {
	frappe.ui.make_app_page({
		parent: wrapper,
		title: "Attendance Dashboard",
		single_column: true,
	});

	// ── State ──────────────────────────────────────────────────────────────────
	let state = { company: null, from_year: 2025, to_year: 2030 };
	let empStatsCache = {}; // cache per company so popover is instant

	// ── CSS ────────────────────────────────────────────────────────────────────
	if (!document.getElementById("att-dash-style")) {
		const style = document.createElement("style");
		style.id = "att-dash-style";
		style.textContent = `
      .att-dash { padding: 20px 24px; font-family: var(--font-stack); }

      /* Filter bar */
      .att-filter-bar {
        display:flex; align-items:center; gap:12px; flex-wrap:wrap;
        background:var(--card-bg,#fff);
        border:1px solid var(--border-color,#e2e8f0);
        border-radius:10px; padding:14px 20px; margin-bottom:22px;
      }
      .att-filter-bar label {
        font-size:11px; font-weight:700; color:var(--text-muted);
        text-transform:uppercase; letter-spacing:.5px;
      }
      .att-filter-bar select {
        border:1px solid var(--border-color,#e2e8f0); border-radius:6px;
        padding:6px 10px; font-size:13px;
        background:var(--input-bg,#f9fafb); color:var(--text-color);
        min-width:160px; cursor:pointer;
      }
      .att-filter-sep { color:var(--border-color); font-size:16px; }

      .att-badge-date {
        margin-left:auto;
        background:#eef2ff; color:#4f46e5;
        border-radius:20px; padding:4px 14px; font-size:12px; font-weight:700;
      }

      /* Matrix card */
      .att-matrix-wrap {
        background:var(--card-bg,#fff);
        border:1px solid var(--border-color,#e2e8f0);
        border-radius:10px; padding:20px; overflow-x:auto;
      }
      .att-matrix-header {
        display:flex; justify-content:space-between;
        align-items:flex-start; margin-bottom:18px;
      }
      .att-matrix-title { font-size:15px; font-weight:700; color:var(--heading-color); }
      .att-matrix-sub   { font-size:12px; color:var(--text-muted); margin-top:2px; }
      .att-legend { display:flex; align-items:center; gap:14px; font-size:12px; color:var(--text-muted); flex-wrap:wrap; }
      .att-legend span { display:flex; align-items:center; gap:5px; }
      .att-dot { width:10px; height:10px; border-radius:50%; display:inline-block; }

      /* Table */
      .att-table { width:100%; border-collapse:separate; border-spacing:0; min-width:960px; }
      .att-table th {
        background:#f8fafc; font-size:11px; font-weight:700;
        text-transform:uppercase; letter-spacing:.4px; color:var(--text-muted);
        padding:10px 8px; text-align:center;
        border-bottom:2px solid var(--border-color,#e2e8f0);
        position:sticky; top:0; z-index:2; white-space:nowrap;
      }
      .att-table th.year-col { text-align:left; min-width:65px; padding-left:14px; }
      .att-table td {
        padding:7px 6px; text-align:center;
        border-bottom:1px solid var(--border-color,#f1f5f9);
        font-size:12px; vertical-align:middle;
      }
      .att-table td.year-label {
        font-weight:700; text-align:left; font-size:13px;
        color:var(--heading-color); background:#f8fafc;
        border-right:2px solid var(--border-color,#e2e8f0);
        position:sticky; left:0; z-index:1; padding-left:14px;
      }
      .att-table tr:last-child td { border-bottom:none; }
      .att-table tr:hover td { background:rgba(79,70,229,.03); }
      .att-table tr:hover td.year-label { background:#f1f5f9; }

      /* Cell chip */
      .att-cell {
        display:inline-flex; align-items:center; justify-content:center;
        border-radius:7px; padding:6px 10px; min-width:58px;
        cursor:pointer; transition:transform .15s, box-shadow .15s;
      }
      .att-cell:hover { transform:scale(1.1); box-shadow:0 2px 8px rgba(0,0,0,.12); }
      .att-cell .cc-present { font-weight:700; font-size:13px; letter-spacing:.3px; }

      /* Heat colours */
      .heat-0 { background:#f1f5f9; color:#94a3b8; }
      .heat-1 { background:#dcfce7; color:#166534; }
      .heat-2 { background:#bbf7d0; color:#15803d; }
      .heat-3 { background:#86efac; color:#166534; }
      .heat-4 { background:#4ade80; color:#14532d; }
      .heat-5 { background:#22c55e; color:#fff;    }

      /* ── Rich Popover ── */
      .att-popover {
        position:fixed; z-index:9999;
        background:var(--card-bg,#fff);
        border:1px solid var(--border-color,#e2e8f0);
        border-radius:12px; padding:0;
        box-shadow:0 12px 40px rgba(0,0,0,.18);
        min-width:250px; max-width:280px;
        font-size:13px; pointer-events:none; overflow:hidden;
      }

      /* dark header with summary numbers */
      .pop-header {
        background:linear-gradient(135deg,#1a1a2e 0%,#16213e 100%);
        color:#fff; padding:13px 16px 12px;
      }
      .pop-header-title { font-size:13px; font-weight:700; margin-bottom:10px; opacity:.9; }
      .pop-header-nums  { display:flex; gap:20px; }
      .pop-num-item     { display:flex; flex-direction:column; align-items:center; }
      .pop-num-val      { font-size:22px; font-weight:800; line-height:1; }
      .pop-num-lbl      { font-size:10px; opacity:.65; text-transform:uppercase; letter-spacing:.4px; margin-top:2px; }
      .pop-num-item.c-green  .pop-num-val { color:#4ade80; }
      .pop-num-item.c-white  .pop-num-val { color:#fff; }
      .pop-num-item.c-blue   .pop-num-val { color:#93c5fd; }

      /* employee totals strip */
      .pop-emp-strip {
        display:flex; border-bottom:1px solid var(--border-color,#f1f5f9);
      }
      .pop-emp-cell {
        flex:1; padding:9px 0; text-align:center;
        border-right:1px solid var(--border-color,#f1f5f9);
      }
      .pop-emp-cell:last-child { border-right:none; }
      .pop-emp-val { font-size:17px; font-weight:700; line-height:1; }
      .pop-emp-lbl { font-size:9px; color:var(--text-muted); text-transform:uppercase; letter-spacing:.3px; margin-top:3px; }
      .pop-emp-cell.c-total    .pop-emp-val { color:#3b82f6; }
      .pop-emp-cell.c-active   .pop-emp-val { color:#22c55e; }
      .pop-emp-cell.c-inactive .pop-emp-val { color:#f43f5e; }

      /* status breakdown rows */
      .pop-status-section { padding:10px 14px 12px; }
      .pop-section-title {
        font-size:10px; font-weight:700; text-transform:uppercase;
        letter-spacing:.4px; color:var(--text-muted); margin-bottom:8px;
      }
      .pop-status-row {
        display:flex; align-items:center; margin-bottom:6px;
      }
      .pop-status-row:last-child { margin-bottom:0; }
      .pop-s-dot  { width:8px; height:8px; border-radius:50%; flex-shrink:0; margin-right:7px; }
      .pop-s-name { font-size:12px; color:var(--text-color); flex:1; }
      .pop-s-bar-wrap { width:70px; height:5px; background:#f1f5f9; border-radius:3px; margin:0 8px; }
      .pop-s-bar      { height:5px; border-radius:3px; }
      .pop-s-cnt      { font-size:12px; font-weight:700; color:var(--heading-color); min-width:20px; text-align:right; }

      .pop-loading { padding:16px; text-align:center; color:var(--text-muted); font-size:12px; }
      .pop-spinner {
        display:inline-block; width:16px; height:16px;
        border:2px solid #e2e8f0; border-top-color:#4f46e5;
        border-radius:50%; animation:att-spin .7s linear infinite; margin-bottom:5px;
      }

      /* empty / loading page */
      .att-empty { text-align:center; padding:60px 0; color:var(--text-muted); font-size:14px; }
      .att-spinner {
        display:inline-block; width:28px; height:28px;
        border:3px solid #e2e8f0; border-top-color:#4f46e5;
        border-radius:50%; animation:att-spin .7s linear infinite; margin-bottom:10px;
      }
      @keyframes att-spin { to { transform:rotate(360deg); } }
    `;
		document.head.appendChild(style);
	}

	// ── Page skeleton (NO stat cards) ─────────────────────────────────────────
	$(wrapper).find(".page-content").html(`
    <div class="att-dash">
      <div class="att-filter-bar">
        <label>Company</label>
        <select id="att-company"><option value="">Loading…</option></select>
        <span class="att-filter-sep">|</span>
        <label>From</label>
        <select id="att-from-year"></select>
        <label>To</label>
        <select id="att-to-year"></select>
<span class="att-badge-date" id="att-badge"></span>
      </div>

      <div class="att-matrix-wrap">
        <div class="att-matrix-header">
          <div>
            <div class="att-matrix-title">Attendance</div>

          </div>
          <div class="att-legend">
            <span><span class="att-dot" style="background:#f1f5f9"></span>No data</span>
            <span><span class="att-dot" style="background:#dcfce7"></span>Low</span>
            <span><span class="att-dot" style="background:#86efac"></span>Mid</span>
            <span><span class="att-dot" style="background:#22c55e"></span>High</span>
          </div>
        </div>
        <div id="att-matrix-body">
          <div class="att-empty">Select a company </div>
        </div>
      </div>
    </div>
    <div class="att-popover" id="att-popover" style="display:none"></div>
  `);

	// ── Constants ──────────────────────────────────────────────────────────────
	const MONTHS = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];
	const STATUS_META = {
		"Present":      "#22c55e",
		"On Tour":      "#3b82f6",
		"Half Day":     "#f59e0b",
		"Absent":       "#f43f5e",
		"Holiday":      "#a78bfa",
		"Weekly Off":   "#94a3b8",
		"LWP":          "#fb923c",
		"Earned Leave": "#06b6d4",
		"Casual Leave": "#8b5cf6",
		"Comp Off":     "#ec4899",
	};

	// ── Year dropdowns ─────────────────────────────────────────────────────────
	(function () {
		const $f = $("#att-from-year"), $t = $("#att-to-year");
		for (let y = 2020; y <= 2035; y++) {
			$f.append(`<option value="${y}" ${y === state.from_year ? "selected":""}>${y}</option>`);
			$t.append(`<option value="${y}" ${y === state.to_year   ? "selected":""}>${y}</option>`);
		}
	})();

	// ── Badge ──────────────────────────────────────────────────────────────────
	(function () {
		const now = new Date();
		$("#att-badge").text(now.toLocaleString("en-IN", { month:"long", year:"numeric" }));
	})();

	// ── Load companies ─────────────────────────────────────────────────────────
	frappe.call({
		method: "saral_hr.saral_hr.page.attendance_dashboard.attendance_dashboard.get_companies",
		callback(r) {
			const $sel = $("#att-company").empty();
			$sel.append('<option value="">— Select Company —</option>');
			(r.message || []).forEach(c => $sel.append(`<option value="${c}">${c}</option>`));
		},
	});

	// ── Heat class ─────────────────────────────────────────────────────────────
	function heatClass(present, total) {
		if (!total) return "heat-0";
		const p = present / total;
		if (p === 0) return "heat-0";
		if (p < 0.2) return "heat-1";
		if (p < 0.4) return "heat-2";
		if (p < 0.6) return "heat-3";
		if (p < 0.8) return "heat-4";
		return "heat-5";
	}

	// ── Render matrix ──────────────────────────────────────────────────────────
	function renderMatrix(matrix) {
		const years = Object.keys(matrix).map(Number).sort();
		if (!years.length) {
			$("#att-matrix-body").html('<div class="att-empty">No attendance records found for this range.</div>');
			return;
		}
		let html = `<table class="att-table">
      <thead><tr>
        <th class="year-col">Year</th>
        ${MONTHS.map(m => `<th>${m}</th>`).join("")}
      </tr></thead><tbody>`;

		years.forEach(year => {
			html += `<tr><td class="year-label">${year}</td>`;
			for (let m = 1; m <= 12; m++) {
				const d = matrix[year][m] || { marked:0, total_emp:0 };
				const cls = heatClass(d.marked, d.total_emp);
				const display = d.total_emp ? `${d.marked}/${d.total_emp}` : "–";
				html += `<td>
          <div class="att-cell ${cls}"
               data-year="${year}" data-month="${m}"
               data-marked="${d.marked}" data-total-emp="${d.total_emp}">
            <span class="cc-present">${display}</span>
          </div>
        </td>`;
			}
			html += "</tr>";
		});
		html += "</tbody></table>";
		$("#att-matrix-body").html(html);
		bindCellHover();
	}

	// ── Popover helpers ────────────────────────────────────────────────────────
	const $pop = $("#att-popover");
	let popTimer = null;

	function headerHtml(year, month, marked, totalEmp) {
		return `
      <div class="pop-header">
        <div class="pop-header-title">${MONTHS[month - 1]} ${year}</div>
        <div class="pop-header-nums">
          <div class="pop-num-item c-white">
            <span class="pop-num-val">${marked} / ${totalEmp}</span>
            <span class="pop-num-lbl">Attendance Marked / Total</span>
          </div>
        </div>
      </div>`;
	}

	function empStripHtml(company) {
		const s = empStatsCache[company] || { total:"…", active:"…", inactive:"…" };
		return `
      <div class="pop-emp-strip">
        <div class="pop-emp-cell c-total">
          <div class="pop-emp-val">${s.total}</div>
          <div class="pop-emp-lbl">Total</div>
        </div>
        <div class="pop-emp-cell c-active">
          <div class="pop-emp-val">${s.active}</div>
          <div class="pop-emp-lbl">Active</div>
        </div>
        <div class="pop-emp-cell c-inactive">
          <div class="pop-emp-val">${s.inactive}</div>
          <div class="pop-emp-lbl">Inactive</div>
        </div>
      </div>`;
	}

	function statusRowsHtml(breakdown) {
		const grandTotal = Object.values(breakdown).reduce((a, b) => a + b, 0) || 1;
		return Object.entries(breakdown)
			.sort((a, b) => b[1] - a[1])
			.map(([status, cnt]) => {
				const color = STATUS_META[status] || "#64748b";
				const pct   = Math.round((cnt / grandTotal) * 100);
				return `
          <div class="pop-status-row">
            <span class="pop-s-dot" style="background:${color}"></span>
            <span class="pop-s-name">${status}</span>
            <div class="pop-s-bar-wrap">
              <div class="pop-s-bar" style="width:${pct}%;background:${color}"></div>
            </div>
            <span class="pop-s-cnt">${cnt}</span>
          </div>`;
			}).join("");
	}

	// ── Bind hover ─────────────────────────────────────────────────────────────
	function bindCellHover() {
		$(document).off("mouseenter.attcell mousemove.attcell mouseleave.attcell");

		$(document).on("mouseenter.attcell", ".att-cell", function (e) {
			const $c      = $(this);
			const year    = $c.data("year");
			const month   = $c.data("month");
			const marked  = $c.data("marked");
			const totalEmp = $c.data("total-emp");

			clearTimeout(popTimer);

			// Build immediately with cached emp stats, loading spinner for status
			$pop.html(
				headerHtml(year, month, marked, totalEmp) +
				empStripHtml(state.company) +
				`<div class="pop-status-section" id="pop-status-inner">
           <div class="pop-section-title">Status Breakdown</div>
           <div class="pop-loading"><div class="pop-spinner"></div><br>Loading…</div>
         </div>`
			).show();
			positionPop(e);

			// Fetch status breakdown async
			frappe.call({
				method: "saral_hr.saral_hr.page.attendance_dashboard.attendance_dashboard.get_status_breakdown",
				args: { company: state.company, year, month },
				callback(r) {
					const breakdown = r.message || {};
					const inner = Object.keys(breakdown).length
						? statusRowsHtml(breakdown)
						: '<div style="color:var(--text-muted);font-size:12px;text-align:center;padding:4px 0">No records for this month</div>';
					$("#pop-status-inner").html(
						`<div class="pop-section-title">Status Breakdown</div>${inner}`
					);
				},
			});
		});

		$(document).on("mousemove.attcell", ".att-cell", positionPop);

		$(document).on("mouseleave.attcell", ".att-cell", function () {
			popTimer = setTimeout(() => $pop.hide(), 200);
		});
	}

	function positionPop(e) {
		const x  = e.clientX + 16;
		const y  = e.clientY + 16;
		const pw = $pop.outerWidth(true)  || 265;
		const ph = $pop.outerHeight(true) || 320;
		$pop.css({
			left: x + pw > window.innerWidth  ? x - pw - 24 : x,
			top:  y + ph > window.innerHeight ? y - ph - 24 : y,
			display: "block",
		});
	}

	// ── Load data ──────────────────────────────────────────────────────────────
	function loadData() {
		const company = $("#att-company").val();
		if (!company) { frappe.msgprint("Please select a company."); return; }

		state.company   = company;
		state.from_year = parseInt($("#att-from-year").val());
		state.to_year   = parseInt($("#att-to-year").val());

		if (state.from_year > state.to_year) {
			frappe.msgprint("'From' year cannot be greater than 'To' year.");
			return;
		}

		// Pre-cache employee stats for instant popover display
		frappe.call({
			method: "saral_hr.saral_hr.page.attendance_dashboard.attendance_dashboard.get_employee_stats",
			args: { company },
			callback(r) {
				empStatsCache[company] = r.message || { total:0, active:0, inactive:0 };
			},
		});

		// Matrix
		$("#att-matrix-body").html(
			'<div class="att-empty"><div class="att-spinner"></div><br>Loading attendance data…</div>'
		);
		frappe.call({
			method: "saral_hr.saral_hr.page.attendance_dashboard.attendance_dashboard.get_attendance_matrix",
			args: { company, from_year: state.from_year, to_year: state.to_year },
			callback(r) { renderMatrix(r.message || {}); },
		});
	}

	// ── Events ─────────────────────────────────────────────────────────────────
	$("#att-company").on("change", loadData);
	$("#att-from-year").on("change", loadData);
	$("#att-to-year").on("change", loadData);
};