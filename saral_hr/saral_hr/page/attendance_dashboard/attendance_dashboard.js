frappe.pages["attendance-dashboard"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: "Attendance Dashboard",
		single_column: true,
	});

	const MONTHS = ["January","February","March","April","May","June","July","August","September","October","November","December"];
	const TODAY  = new Date();

	// ── Exact statuses from Attendance doctype ────────────────────────────────
	// Present | Earned Comp Off | On Tour | Absent | Half Day | Holiday
	// Weekly Off | LWP | Earned Leave | Casual Leave | Comp Off

	const STATUS_META = {
		"Present":         { color:"#16a34a", bg:"#f0fdf4", border:"#86efac", text:"#15803d" },
		"On Tour":         { color:"#0284c7", bg:"#f0f9ff", border:"#7dd3fc", text:"#0369a1" },
		"Earned Comp Off": { color:"#d97706", bg:"#fffbeb", border:"#fcd34d", text:"#92400e" },
		"Earned Leave":    { color:"#7c3aed", bg:"#f5f3ff", border:"#c4b5fd", text:"#6d28d9" },
		"Casual Leave":    { color:"#9333ea", bg:"#faf5ff", border:"#d8b4fe", text:"#7e22ce" },
		"Comp Off":        { color:"#0891b2", bg:"#ecfeff", border:"#a5f3fc", text:"#0e7490" },
		"Half Day":        { color:"#f59e0b", bg:"#fefce8", border:"#fde68a", text:"#b45309" },
		"Absent":          { color:"#dc2626", bg:"#fef2f2", border:"#fca5a5", text:"#b91c1c" },
		"LWP":             { color:"#991b1b", bg:"#fff1f2", border:"#fda4af", text:"#881337" },
		"Holiday":         { color:"#0e7490", bg:"#ecfeff", border:"#a5f3fc", text:"#155e75" },
		"Weekly Off":      { color:"#64748b", bg:"#f8fafc", border:"#cbd5e1", text:"#475569" },
		"Not Marked":      { color:"#9ca3af", bg:"#f9fafb", border:"#e5e7eb", text:"#6b7280" },
	};

	// ── Groupings for summary cards ───────────────────────────────────────────
	// "Physically Present" — actually at work
	const PHYSICALLY_PRESENT = new Set(["Present", "On Tour", "Earned Comp Off"]);
	// "On Leave" — approved paid leave
	const ON_LEAVE            = new Set(["Earned Leave", "Casual Leave", "Comp Off"]);
	// "Unpaid / Penalised" — deducted from salary
	const UNPAID              = new Set(["Absent", "LWP"]);
	// All statuses that count as "marked" (attendance was recorded)
	const ALL_PRESENT         = new Set([...PHYSICALLY_PRESENT, ...ON_LEAVE, "Half Day"]);

	let state = {
		company:    null,
		department: "",
		view:       "daily",
		date:       frappe.datetime.get_today(),
		year:       String(TODAY.getFullYear()),
		month:      MONTHS[TODAY.getMonth()],
		activeDept: null,
	};

	// ── Styles ────────────────────────────────────────────────────────────────
	if (!document.getElementById("ap-styles")) {
		$(`<style id="ap-styles">
		.ap-wrap * { box-sizing: border-box; }

		.ap-filterbar {
			background: var(--card-bg);
			border-bottom: 1px solid var(--border-color);
			padding: 12px 20px;
			display: flex; align-items: flex-end; gap: 14px; flex-wrap: nowrap;
			position: sticky; top: 0; z-index: 50;
			box-shadow: 0 1px 4px rgba(0,0,0,.06);
			overflow-x: auto;
		}
		.ap-fi { display: flex; flex-direction: column; gap: 4px; flex-shrink: 0; }
		.ap-fi-grow { flex: 1; min-width: 160px; }
		.ap-label {
			font-size: 10px; font-weight: 700; color: var(--text-muted);
			text-transform: uppercase; letter-spacing: .5px;
		}
		.ap-ctrl {
			height: 34px; font-size: 13px; font-weight: 500;
			border: 1px solid var(--border-color); border-radius: 6px;
			background: var(--bg-color); color: var(--text-color);
			padding: 0 10px; outline: none; transition: border-color .15s;
		}
		.ap-ctrl:focus { border-color: var(--primary); }
		select.ap-ctrl { cursor: pointer; min-width: 120px; }
		input[type=date].ap-ctrl { min-width: 150px; cursor: pointer; }

		.ap-view-grp {
			display: flex; border: 1px solid var(--border-color);
			border-radius: 6px; overflow: hidden; height: 34px;
		}
		.ap-vtab {
			padding: 0 16px; font-size: 12px; font-weight: 700;
			border: none; background: var(--bg-color); color: var(--text-muted);
			cursor: pointer; transition: all .15s; white-space: nowrap;
			border-right: 1px solid var(--border-color);
		}
		.ap-vtab:last-child { border-right: none; }
		.ap-vtab:hover { background: var(--highlight-color); color: var(--text-color); }
		.ap-vtab.active { background: var(--primary); color: #fff; }

		.ap-yr-grp { display: flex; gap: 4px; height: 34px; align-items: center; }
		.ap-yr-pill {
			padding: 4px 12px; border-radius: 6px; font-size: 13px; font-weight: 700;
			border: 1px solid var(--border-color); background: var(--bg-color);
			color: var(--text-muted); cursor: pointer; transition: all .15s; white-space: nowrap;
		}
		.ap-yr-pill:hover  { border-color: var(--primary); color: var(--primary); }
		.ap-yr-pill.active { background: var(--primary); border-color: var(--primary); color: #fff; }

		.ap-nav-grp { display: flex; align-items: center; gap: 5px; height: 34px; }
		.ap-nav-btn {
			width: 34px; height: 34px; border: 1px solid var(--border-color);
			border-radius: 6px; background: var(--bg-color); cursor: pointer;
			font-size: 16px; color: var(--text-color); display: flex;
			align-items: center; justify-content: center; transition: all .15s;
			flex-shrink: 0;
		}
		.ap-nav-btn:hover { background: var(--primary); color: #fff; border-color: var(--primary); }

		.ap-infostrip {
			padding: 7px 20px; font-size: 12px; color: var(--text-muted);
			background: var(--subtle-fg); border-bottom: 1px solid var(--border-color);
			display: flex; align-items: center; gap: 8px;
		}
		.ap-infostrip strong { color: var(--text-color); }
		.ap-live-dot {
			width: 7px; height: 7px; border-radius: 50%; background: #22c55e;
			flex-shrink: 0; animation: ap-pulse 2s infinite;
		}
		@keyframes ap-pulse { 0%,100%{opacity:1} 50%{opacity:.4} }

		.ap-main { padding: 18px 20px 40px; }

		/* ── Summary cards ── */
		.ap-cards {
			display: grid;
			grid-template-columns: repeat(auto-fill, minmax(130px,1fr));
			gap: 10px; margin-bottom: 20px;
		}
		.ap-card {
			border-radius: 10px; padding: 14px 14px 12px; color: #fff;
			cursor: pointer; user-select: none;
			transition: transform .15s, box-shadow .15s, opacity .15s;
			position: relative; overflow: hidden;
		}
		.ap-card::after {
			content:""; position:absolute; top:-18px; right:-18px;
			width:56px; height:56px; border-radius:50%; background:rgba(255,255,255,.1);
		}
		.ap-card:hover  { transform: translateY(-2px); box-shadow: 0 6px 18px rgba(0,0,0,.14); }
		.ap-card.dim    { opacity: .4; }
		.ap-card.active { transform: translateY(-2px); box-shadow: 0 6px 18px rgba(0,0,0,.22); outline: 2px solid rgba(255,255,255,.55); outline-offset: -2px; }
		.ap-card-icon  { font-size: 16px; margin-bottom: 6px; }
		.ap-card-num   { font-size: 28px; font-weight: 900; line-height: 1; margin-bottom: 3px; }
		.ap-card-label { font-size: 10px; font-weight: 700; text-transform: uppercase; letter-spacing: .4px; opacity: .85; }

		/* ── Layout panels ── */
		.ap-two-col { display: grid; grid-template-columns: 1.1fr 1fr; gap: 14px; margin-bottom: 14px; }
		@media(max-width:800px){ .ap-two-col { grid-template-columns: 1fr; } }

		.ap-panel {
			background: var(--card-bg); border: 1px solid var(--border-color);
			border-radius: 10px; overflow: hidden;
			box-shadow: 0 1px 4px rgba(0,0,0,.04); margin-bottom: 14px;
		}
		.ap-panel-hd {
			padding: 11px 16px; border-bottom: 1px solid var(--border-color);
			display: flex; align-items: center; justify-content: space-between;
		}
		.ap-panel-title { font-size: 13px; font-weight: 700; color: var(--text-color); }
		.ap-badge {
			font-size: 11px; font-weight: 700; padding: 2px 9px;
			border-radius: 10px; color: #fff;
		}

		/* Not-marked panel accent */
		.ap-nm { border-color: #fed7aa; }
		.ap-nm .ap-panel-hd { background: #fff7ed; border-bottom-color: #fed7aa; }
		.ap-nm .ap-panel-title { color: #c2410c; }

		/* ── Search ── */
		.ap-search-wrap { padding: 8px 14px; border-bottom: 1px solid var(--border-color); position: relative; }
		.ap-search-ico { position:absolute; left:22px; top:50%; transform:translateY(-50%); color:var(--text-muted); pointer-events:none; }
		.ap-search {
			width:100%; height:30px; border:1px solid var(--border-color); border-radius:6px;
			padding:0 8px 0 30px; font-size:12px; background:var(--bg-color);
			color:var(--text-color); outline:none;
		}
		.ap-search:focus { border-color:var(--primary); }

		/* ── Employee rows ── */
		.ap-emp-row {
			display:flex; align-items:center; gap:10px; padding:10px 16px;
			border-bottom:1px solid var(--border-color); cursor:pointer; transition:background .1s;
		}
		.ap-emp-row:last-child { border-bottom:none; }
		.ap-emp-row:hover { background:var(--highlight-color); }
		.ap-av {
			width:34px; height:34px; border-radius:50%; flex-shrink:0;
			display:flex; align-items:center; justify-content:center;
			font-size:12px; font-weight:700; color:#fff;
		}
		.ap-emp-info { flex:1; min-width:0; }
		.ap-emp-name { font-size:13px; font-weight:600; color:var(--text-color); white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
		.ap-emp-meta { font-size:11px; color:var(--text-muted); }

		/* ── Department pills ── */
		.ap-dept-strip { display:flex; gap:5px; flex-wrap:wrap; padding:8px 14px; border-bottom:1px solid var(--border-color); }
		.ap-dpill {
			padding:3px 10px; border-radius:14px; font-size:11px; font-weight:600;
			border:1px solid var(--border-color); background:var(--card-bg);
			color:var(--text-muted); cursor:pointer; transition:all .12s;
		}
		.ap-dpill:hover { border-color:var(--primary); color:var(--primary); }
		.ap-dpill.active { background:var(--primary); border-color:var(--primary); color:#fff; }

		/* ── Status breakdown chips ── */
		.ap-bk-wrap { display:flex; flex-wrap:wrap; gap:7px; padding:12px 14px; }
		.ap-bk-chip {
			display:flex; align-items:center; gap:6px; padding:6px 11px;
			border-radius:7px; border:1px solid transparent;
		}
		.ap-bk-dot  { width:8px; height:8px; border-radius:50%; flex-shrink:0; }
		.ap-bk-cnt  { font-size:14px; font-weight:800; }
		.ap-bk-lbl  { font-size:11px; font-weight:600; }

		/* ── Bar chart ── */
		.ap-chart { padding:14px 16px; }
		.ap-bars { display:flex; align-items:flex-end; gap:3px; height:90px; overflow-x:auto; padding-bottom:2px; }
		.ap-bc { display:flex; flex-direction:column; align-items:center; gap:2px; flex-shrink:0; width:20px; }
		.ap-bs { width:14px; border-radius:2px 2px 0 0; min-height:2px; cursor:pointer; transition:opacity .1s; }
		.ap-bs:hover { opacity:.7; }
		.ap-bd { font-size:8px; color:var(--text-muted); font-weight:600; }
		.ap-chart-leg { display:flex; gap:12px; margin-top:8px; flex-wrap:wrap; }
		.ap-cl-item { display:flex; align-items:center; gap:4px; font-size:11px; color:var(--text-muted); }
		.ap-cl-dot  { width:9px; height:9px; border-radius:2px; }

		/* ── Holiday rows ── */
		.ap-hol-row {
			display:flex; align-items:center; gap:10px; padding:9px 16px;
			border-bottom:1px solid var(--border-color);
		}
		.ap-hol-row:last-child { border-bottom:none; }
		.ap-hol-dot  { width:8px; height:8px; border-radius:50%; background:#0e7490; flex-shrink:0; }
		.ap-hol-name { font-size:13px; font-weight:600; color:var(--text-color); flex:1; }
		.ap-hol-day  { font-size:11px; color:var(--text-muted); }
		.ap-hol-date { font-size:11px; color:var(--text-muted); white-space:nowrap; }

		/* ── Attendance % bar ── */
		.ap-pct-bg   { height:5px; background:var(--border-color); border-radius:3px; overflow:hidden; flex:1; }
		.ap-pct-fill { height:100%; border-radius:3px; transition:width .5s; }

		/* ── Yearly table ── */
		.ap-yr-tbl { width:100%; border-collapse:collapse; font-size:13px; }
		.ap-yr-tbl thead th {
			padding:8px 14px; text-align:left; font-size:10px; font-weight:800;
			color:var(--text-muted); text-transform:uppercase; letter-spacing:.4px;
			background:var(--subtle-fg); border-bottom:1px solid var(--border-color);
		}
		.ap-yr-tbl thead th:not(:first-child) { text-align:center; }
		.ap-yr-tbl tbody tr { border-bottom:1px solid var(--border-color); cursor:pointer; transition:background .1s; }
		.ap-yr-tbl tbody tr:hover { background:var(--highlight-color); }
		.ap-yr-tbl tbody td { padding:10px 14px; }
		.ap-yr-tbl tbody td:not(:first-child):not(:last-child) { text-align:center; }

		/* ── Employee detail drawer ── */
		.ap-overlay {
			position:fixed; inset:0; background:rgba(0,0,0,.45);
			z-index:1000; display:flex; align-items:center; justify-content:center;
			backdrop-filter:blur(2px);
		}
		.ap-drawer {
			background:var(--card-bg); border-radius:12px;
			width:680px; max-width:95vw; max-height:88vh;
			overflow:hidden; display:flex; flex-direction:column;
			box-shadow:0 20px 60px rgba(0,0,0,.2);
		}
		.ap-drawer-hd {
			padding:16px 20px; border-bottom:1px solid var(--border-color);
			display:flex; align-items:center; justify-content:space-between; flex-shrink:0;
		}
		.ap-drawer-title { font-size:15px; font-weight:800; color:var(--text-color); }
		.ap-drawer-sub   { font-size:11px; color:var(--text-muted); margin-top:2px; }
		.ap-drawer-close {
			width:28px; height:28px; border-radius:50%; background:var(--subtle-fg);
			display:flex; align-items:center; justify-content:center;
			cursor:pointer; font-size:16px; color:var(--text-muted); transition:all .15s;
		}
		.ap-drawer-close:hover { background:var(--primary); color:#fff; }
		.ap-drawer-body { overflow-y:auto; padding:18px 20px; flex:1; }

		.ap-ds-row { display:flex; gap:8px; flex-wrap:wrap; margin-bottom:16px; }
		.ap-ds {
			flex:1; min-width:70px; padding:10px 8px; border-radius:8px;
			text-align:center; border:1px solid var(--border-color);
		}
		.ap-ds-val { font-size:18px; font-weight:800; line-height:1; }
		.ap-ds-lbl { font-size:9px; font-weight:700; text-transform:uppercase; color:var(--text-muted); margin-top:3px; }

		/* ── Heatmap calendar ── */
		.ap-cal      { display:grid; grid-template-columns:repeat(7,32px); gap:3px; width:fit-content; margin:0 auto; }
		.ap-cal-lbl  { text-align:center; font-size:10px; font-weight:700; color:var(--text-muted); padding:2px 0; width:32px; }
		.ap-cal-cell {
			width:32px; height:32px; border-radius:5px; display:flex; align-items:center;
			justify-content:center; font-size:11px; font-weight:700;
			cursor:default; transition:transform .1s;
		}
		.ap-cal-cell:hover { transform:scale(1.1); z-index:1; position:relative; }
		.ap-cal-today { box-shadow:0 0 0 2px #fff, 0 0 0 3px var(--primary); }

		/* ── Month picker popup ── */
		.ap-mypicker-body {
			position: absolute; background: var(--card-bg);
			border: 1px solid var(--border-color);
			border-radius: 10px; box-shadow: 0 8px 28px rgba(0,0,0,.16);
			z-index: 9999; padding: 14px; width: 250px; display: none;
		}
		.ap-myp-trigger {
			height: 34px; padding: 0 12px; border: 1px solid var(--border-color);
			border-radius: 6px; background: var(--bg-color); color: var(--text-color);
			cursor: pointer; display: flex; align-items: center; gap: 8px;
			font-size: 13px; font-weight: 700; transition: border-color .15s;
			min-width: 155px; justify-content: space-between;
		}
		.ap-myp-trigger:hover { border-color: var(--primary); }
		.ap-myp-arrow  { font-size: 10px; opacity: .5; }
		.ap-myp-yr-row {
			display: flex; align-items: center; justify-content: space-between;
			margin-bottom: 12px;
		}
		.ap-myp-yr-btn {
			width: 28px; height: 28px; border-radius: 6px;
			border: 1px solid var(--border-color); background: var(--bg-color);
			cursor: pointer; font-size: 14px; display: flex;
			align-items: center; justify-content: center; transition: all .15s;
		}
		.ap-myp-yr-btn:hover { background: var(--primary); color: #fff; border-color: var(--primary); }
		.ap-myp-yr-val { font-size: 15px; font-weight: 800; color: var(--text-color); }
		.ap-myp-months { display: grid; grid-template-columns: repeat(3,1fr); gap: 5px; }
		.ap-myp-month {
			padding: 7px 4px; border-radius: 7px; text-align: center;
			font-size: 12px; font-weight: 600; cursor: pointer;
			border: 1.5px solid var(--border-color); color: var(--text-color);
			transition: all .15s; background: var(--bg-color);
		}
		.ap-myp-month:hover  { border-color: var(--primary); color: var(--primary); }
		.ap-myp-month.active { background: var(--primary); border-color: var(--primary); color: #fff; }

		/* ── Monthly top 3 metric cards ── */
		.ap-monthly-summary {
			display: grid; grid-template-columns: repeat(3,1fr);
			gap: 12px; margin-bottom: 18px;
		}
		.ap-ms-card {
			border: 1.5px solid; border-radius: 10px;
			padding: 16px 18px; display: flex; flex-direction: column; gap: 4px;
		}
		.ap-ms-icon  { font-size: 20px; margin-bottom: 4px; }
		.ap-ms-val   { font-size: 34px; font-weight: 900; line-height: 1; }
		.ap-ms-label { font-size: 13px; font-weight: 700; color: var(--text-color); margin-top: 2px; }
		.ap-ms-sub   { font-size: 11px; color: var(--text-muted); }

		/* ── Tooltip ── */
		.ap-tip {
			position:fixed; background:rgba(10,10,10,.88); color:#fff;
			font-size:11px; padding:5px 10px; border-radius:5px;
			pointer-events:none; z-index:9999; white-space:nowrap; display:none;
		}

		/* ── Skeletons ── */
		.ap-sk {
			background:linear-gradient(90deg,var(--subtle-fg) 25%,var(--border-color) 50%,var(--subtle-fg) 75%);
			background-size:200% 100%; animation:apsh 1.4s infinite; border-radius:5px;
		}
		@keyframes apsh{0%{background-position:200% 0}100%{background-position:-200% 0}}

		.ap-empty { text-align:center; padding:28px 16px; color:var(--text-muted); font-size:13px; }
		</style>`).appendTo("head");
	}

	if (!document.querySelector(".ap-tip")) $(`<div class="ap-tip"></div>`).appendTo("body");
	const tip     = (txt,e) => $(".ap-tip").text(txt).css({display:"block",left:e.clientX+12,top:e.clientY-30});
	const hideTip = () => $(".ap-tip").hide();

	// ── Build page layout ─────────────────────────────────────────────────────
	const $wrap = $(`<div class="ap-wrap"></div>`).appendTo(page.main);
	const $fb   = $(`<div class="ap-filterbar"></div>`).appendTo($wrap);

	// Company filter
	const $coFi = $(`<div class="ap-fi ap-fi-grow"><span class="ap-label">Company</span><select class="ap-ctrl ap-co"></select></div>`).appendTo($fb);
	const $co   = $coFi.find(".ap-co");
	$co.append(`<option value="">— Select Company —</option>`);
	frappe.db.get_list("Company",{fields:["name"],limit:200,order_by:"name asc"}).then(rows=>{
		rows.forEach(r=>$co.append(`<option value="${r.name}">${r.name}</option>`));
	});
	$co.on("change",()=>{ state.company=$co.val(); state.department=""; state.activeDept=null; if(state.company){ loadDepts(); autoLoad(); } });

	// View toggle
	const $vFi = $(`<div class="ap-fi"><span class="ap-label">View</span>
		<div class="ap-view-grp">
			<button class="ap-vtab active" data-v="daily">Daily</button>
			<button class="ap-vtab" data-v="monthly">Monthly</button>
			<button class="ap-vtab" data-v="yearly">Yearly</button>
		</div>
	</div>`).appendTo($fb);
	$vFi.find(".ap-vtab").on("click",function(){
		const v=$(this).data("v");
		if(v===state.view) return;
		state.view=v;
		$vFi.find(".ap-vtab").removeClass("active"); $(this).addClass("active");
		renderPeriodFields();
		if(state.company) autoLoad();
	});

	// Period field container
	const $pFi = $(`<div class="ap-fi" id="ap-period-fi"><span class="ap-label">Period</span><div class="ap-period-fields" style="display:flex;align-items:center;gap:6px;height:34px;"></div></div>`).appendTo($fb);
	const $pf  = $pFi.find(".ap-period-fields");

	function renderPeriodFields(){
		$pf.empty();
		if(state.view==="daily"){
			const $prev=$(`<button class="ap-nav-btn">‹</button>`);
			const $inp =$(`<input type="date" class="ap-ctrl" value="${state.date}">`);
			const $next=$(`<button class="ap-nav-btn">›</button>`);
			$prev.on("click",()=>{ shiftDate(-1); $inp.val(state.date); if(state.company) autoLoad(); });
			$next.on("click",()=>{ shiftDate(+1); $inp.val(state.date); if(state.company) autoLoad(); });
			$inp.on("change",function(){ state.date=$(this).val(); if(state.company) autoLoad(); });
			$pf.append($prev,$inp,$next);
		} else if(state.view==="monthly"){
			const $prev=$(`<button class="ap-nav-btn">‹</button>`);
			const $next=$(`<button class="ap-nav-btn">›</button>`);
			const $trigger=$(`<button class="ap-myp-trigger">
				<span class="ap-myp-lbl">${state.month} ${state.year}</span>
				<span class="ap-myp-arrow">▼</span>
			</button>`);
			$(".ap-mypicker-body").remove();
			const $pop=$(`<div class="ap-mypicker-body"></div>`).appendTo("body");
			let mpYear=state.year;
			function buildMonthPicker(){
				$pop.empty();
				const $yr=$(`<div class="ap-myp-yr-row">
					<button class="ap-myp-yr-btn">‹</button>
					<span class="ap-myp-yr-val">${mpYear}</span>
					<button class="ap-myp-yr-btn">›</button>
				</div>`).appendTo($pop);
				$yr.find(".ap-myp-yr-btn").eq(0).on("click",(e)=>{ e.stopPropagation(); mpYear=String(parseInt(mpYear)-1); buildMonthPicker(); });
				$yr.find(".ap-myp-yr-btn").eq(1).on("click",(e)=>{ e.stopPropagation(); mpYear=String(parseInt(mpYear)+1); buildMonthPicker(); });
				const $mg=$(`<div class="ap-myp-months"></div>`).appendTo($pop);
				MONTHS.forEach(m=>{
					const $mb=$(`<div class="ap-myp-month ${m===state.month&&mpYear===state.year?"active":""}">${m.slice(0,3)}</div>`);
					$mb.on("click",(e)=>{
						e.stopPropagation();
						state.month=m; state.year=mpYear;
						$trigger.find(".ap-myp-lbl").text(`${state.month} ${state.year}`);
						$pop.hide();
						if(state.company) autoLoad();
					});
					$mg.append($mb);
				});
			}
			function positionPop(){
				const r=$trigger[0].getBoundingClientRect();
				$pop.css({ top: r.bottom+window.scrollY+6, left: r.left+window.scrollX });
			}
			$trigger.on("click",(e)=>{
				e.stopPropagation();
				if($pop.is(":visible")){ $pop.hide(); return; }
				mpYear=state.year; buildMonthPicker(); positionPop(); $pop.show();
			});
			$(document).off("mousedown.mypicker").on("mousedown.mypicker",(e)=>{
				if(!$(e.target).closest($pop).length && !$(e.target).closest($trigger).length) $pop.hide();
			});
			$prev.on("click",()=>{ shiftMonth(-1); $trigger.find(".ap-myp-lbl").text(`${state.month} ${state.year}`); if(state.company) autoLoad(); });
			$next.on("click",()=>{ shiftMonth(+1); $trigger.find(".ap-myp-lbl").text(`${state.month} ${state.year}`); if(state.company) autoLoad(); });
			$pf.append($prev,$trigger,$next);
		} else {
			const $prev=$(`<button class="ap-nav-btn">‹</button>`);
			const $yrGrp=$(`<div class="ap-yr-grp"></div>`);
			const $next=$(`<button class="ap-nav-btn">›</button>`);
			buildYrPills($yrGrp);
			$prev.on("click",()=>{ state.year=String(parseInt(state.year)-1); buildYrPills($yrGrp); if(state.company) autoLoad(); });
			$next.on("click",()=>{ state.year=String(parseInt(state.year)+1); buildYrPills($yrGrp); if(state.company) autoLoad(); });
			$pf.append($prev,$yrGrp,$next);
		}
	}

	function buildYrPills($grp){
		$grp.empty();
		const cur=parseInt(state.year);
		[cur-1,cur,cur+1].forEach(y=>{
			const $p=$(`<span class="ap-yr-pill ${String(y)===state.year?"active":""}">${y}</span>`);
			$p.on("click",()=>{ state.year=String(y); buildYrPills($grp); if(state.company) autoLoad(); });
			$grp.append($p);
		});
	}

	function shiftDate(d){ const dt=new Date(state.date); dt.setDate(dt.getDate()+d); state.date=dt.toISOString().split("T")[0]; }
	function shiftMonth(d){
		let mi=MONTHS.indexOf(state.month)+d;
		if(mi<0){ mi=11; state.year=String(parseInt(state.year)-1); }
		if(mi>11){ mi=0;  state.year=String(parseInt(state.year)+1); }
		state.month=MONTHS[mi];
	}

	// Department filter
	const $dFi = $(`<div class="ap-fi"><span class="ap-label">Department</span><select class="ap-ctrl ap-dept"><option value="">All Departments</option></select></div>`).appendTo($fb);
	const $dept = $dFi.find(".ap-dept");
	$dept.on("change",()=>{ state.department=$dept.val(); state.activeDept=$dept.val()||null; if(state.company) autoLoad(); });

	function loadDepts(){
		frappe.call({
			method:"saral_hr.saral_hr.page.attendance_dashboard.attendance_dashboard.get_filter_meta",
			args:{company:state.company},
			callback(r){
				const depts=(r.message&&r.message.departments)||[];
				$dept.html(`<option value="">All Departments</option>`);
				depts.forEach(d=>$dept.append(`<option value="${d}">${d}</option>`));
			}
		});
	}

	const $info = $(`<div class="ap-infostrip"><div class="ap-live-dot"></div><span class="ap-info-txt">Select a company to get started.</span></div>`).appendTo($wrap);
	const $main = $(`<div class="ap-main"></div>`).appendTo($wrap);
	$main.html(`<div style="text-align:center;padding:60px 20px;color:var(--text-muted);">
		<div style="font-size:48px;margin-bottom:14px;">📋</div>
		<div style="font-size:15px;font-weight:700;color:var(--text-color);margin-bottom:5px;">Attendance Dashboard</div>
		<div style="font-size:13px;">Select a company above — today's data loads automatically.</div>
	</div>`);

	renderPeriodFields();

	function autoLoad(){
		if(!state.company) return;
		if(state.view==="daily")   loadDaily();
		if(state.view==="monthly") loadMonthly();
		if(state.view==="yearly")  loadYearly();
	}

	function setInfo(txt){ $info.find(".ap-info-txt").html(txt); }

	// ═══════════════════════════════════════════════════════════════════════════
	//  DAILY VIEW
	// ═══════════════════════════════════════════════════════════════════════════
	function loadDaily(){
		$main.html(skelCards(8)+`<div class="ap-two-col">${skelPanel()}${skelPanel()}</div>`);
		frappe.call({
			method:"saral_hr.saral_hr.page.attendance_dashboard.attendance_dashboard.get_daily_summary",
			args:{company:state.company, att_date:state.date, department:state.department},
			callback(r){ renderDaily(r.message); },
			error(){ $main.html(`<div class="ap-empty">⚠️ Failed to load data.</div>`); }
		});
	}

	function renderDaily(d){
		$main.empty();
		const isToday = d.date === frappe.datetime.get_today();
		setInfo(`<strong>${state.company}</strong> &nbsp;·&nbsp; ${frappe.datetime.str_to_user(d.date)}${isToday?" &nbsp;<strong style='color:#16a34a;'>Today</strong>":""} &nbsp;·&nbsp; ${d.total_active} active employees`);

		// Summary cards — grouped for HR clarity
		const defs = [
			{ icon:"👥", val:d.total_active,           label:"Total Active",  bg:"#1e40af", f:null },
			{ icon:"✔️", val:d.marked_count,            label:"Marked",        bg:"#0f766e", f:"marked" },
			{ icon:"⚠️", val:d.not_marked_count,        label:"Not Marked",    bg:"#92400e", f:"nm" },
			{ icon:"🏢", val:d.physically_present,      label:"At Work",       bg:"#15803d", f:"present" },
			{ icon:"🌴", val:d.on_leave_count,           label:"On Leave",      bg:"#7c3aed", f:"leave" },
			{ icon:"🌗", val:d.half_day_count,           label:"Half Day",      bg:"#b45309", f:"hd" },
			{ icon:"❌", val:d.unpaid_count,             label:"Absent / LWP",  bg:"#b91c1c", f:"absent" },
			{ icon:"🎉", val:d.holiday_count,            label:"Holiday",       bg:"#0e7490", f:null },
		];

		const $cards = $(`<div class="ap-cards"></div>`).appendTo($main);
		let activeF = null;
		defs.forEach(c=>{
			const $c=$(`<div class="ap-card" style="background:${c.bg};">
				<div class="ap-card-icon">${c.icon}</div>
				<div class="ap-card-num" data-t="${c.val}">0</div>
				<div class="ap-card-label">${c.label}</div>
			</div>`);
			if(c.f){
				$c.on("click",()=>{
					activeF = activeF===c.f ? null : c.f;
					$cards.find(".ap-card").removeClass("active dim");
					if(activeF){ $cards.find(".ap-card").addClass("dim"); $c.removeClass("dim").addClass("active"); }
					renderDailyPanels(d, activeF);
				});
			}
			$cards.append($c);
		});
		animNums($cards);
		renderDailyPanels(d, null);
	}

	function renderDailyPanels(d, activeF){
		$main.find(".ap-daily-panels").remove();
		const $topRow = $(`<div class="ap-two-col ap-daily-panels"></div>`).appendTo($main);

		function buildEmpPanel(title, badgeColor, badgeNum, empList, emptyMsg, emptyColor){
			const $panel = $(`<div class="ap-panel ${badgeColor==="#c2410c"?"ap-nm":""}"></div>`);
			$(`<div class="ap-panel-hd">
				<span class="ap-panel-title">${title}</span>
				<span class="ap-badge" style="background:${badgeColor};">${badgeNum}</span>
			</div>`).appendTo($panel);
			const $body = $(`<div></div>`).appendTo($panel);
			if(!empList.length){
				$body.html(`<div class="ap-empty" style="color:${emptyColor||"var(--text-muted)"};">${emptyMsg}</div>`);
				return $panel;
			}
			const depts = [...new Set(empList.map(e=>e.department).filter(Boolean))];
			if(depts.length>1){
				const $ds = $(`<div class="ap-dept-strip"></div>`).appendTo($body);
				const $all = $(`<span class="ap-dpill ${!state.activeDept?"active":""}">All</span>`).appendTo($ds);
				$all.on("click",()=>{ state.activeDept=null; renderDailyPanels(d,activeF); });
				depts.forEach(dept=>{
					const $p=$(`<span class="ap-dpill ${state.activeDept===dept?"active":""}">${dept}</span>`).appendTo($ds);
					$p.on("click",()=>{ state.activeDept=dept; renderDailyPanels(d,activeF); });
				});
			}
			const filtered = state.activeDept ? empList.filter(e=>e.department===state.activeDept) : empList;
			const $sw = buildSearch($body);
			const $list = $(`<div style="max-height:300px;overflow-y:auto;"></div>`).appendTo($body);
			const draw = (items)=>{
				$list.empty();
				if(!items.length){ $list.html(`<div class="ap-empty">No results.</div>`); return; }
				items.forEach(e=>{
					const ini=initials(e.name), hue=hueFor(e.employee||e.name);
					const sm=e.status?STATUS_META[e.status]||{color:"#94a3b8",bg:"#f8fafc",border:"#e2e8f0",text:"#475569"}:null;
					$list.append(`<div class="ap-emp-row">
						<div class="ap-av" style="background:hsl(${hue},62%,44%);">${ini}</div>
						<div class="ap-emp-info">
							<div class="ap-emp-name">${e.name}</div>
							<div class="ap-emp-meta">${e.department||"—"} · ${e.designation||"—"}</div>
						</div>
						${sm?`<span style="font-size:11px;font-weight:700;padding:2px 8px;border-radius:5px;background:${sm.bg};color:${sm.color};border:1px solid ${sm.border};white-space:nowrap;flex-shrink:0;">${e.status}</span>`:""}
					</div>`);
				});
			};
			draw(filtered);
			$sw.find(".ap-search").on("input",function(){
				const q=$(this).val().toLowerCase();
				const base=state.activeDept?empList.filter(e=>e.department===state.activeDept):empList;
				draw(q?base.filter(e=>(e.name||"").toLowerCase().includes(q)):base);
			});
			return $panel;
		}

		const nmList     = d.not_marked_list  || [];
		const markedList = d.marked_list       || [];

		// Filter marked list based on activeF
		let filteredMarked = markedList;
		if(activeF==="present") filteredMarked = markedList.filter(e=>PHYSICALLY_PRESENT.has(e.status));
		else if(activeF==="leave") filteredMarked = markedList.filter(e=>ON_LEAVE.has(e.status));
		else if(activeF==="hd")    filteredMarked = markedList.filter(e=>e.status==="Half Day");
		else if(activeF==="absent") filteredMarked = markedList.filter(e=>UNPAID.has(e.status));
		else if(activeF==="nm")    filteredMarked = [];

		const showNm = (!activeF || activeF==="nm");
		$topRow.append(buildEmpPanel("⚠️ Not Marked",   "#c2410c", showNm?nmList.length:0,    showNm?nmList:[], "✅ All employees marked for this date!", "#16a34a"));
		$topRow.append(buildEmpPanel("✔️ Attendance Log","#0f766e", filteredMarked.length, filteredMarked, "No employees marked yet.",""));

		// Status breakdown
		const $bd = $(`<div class="ap-panel ap-daily-panels"></div>`).appendTo($main);
		$(`<div class="ap-panel-hd"><span class="ap-panel-title">📊 Status Breakdown</span></div>`).appendTo($bd);
		const bk = d.status_breakdown || {};
		if(!Object.keys(bk).length){ $bd.append(`<div class="ap-empty">No attendance records yet.</div>`); }
		else {
			const $bw = $(`<div class="ap-bk-wrap"></div>`).appendTo($bd);
			Object.entries(bk).sort((a,b)=>b[1]-a[1]).forEach(([st,cnt])=>{
				const m = STATUS_META[st]||{color:"#94a3b8",bg:"#f8fafc",border:"#e2e8f0",text:"#475569"};
				$bw.append(`<div class="ap-bk-chip" style="background:${m.bg};border-color:${m.border};">
					<span class="ap-bk-dot" style="background:${m.color};"></span>
					<span class="ap-bk-cnt" style="color:${m.color};">${cnt}</span>
					<span class="ap-bk-lbl" style="color:${m.text};">${st}</span>
				</div>`);
			});
		}
	}

	// ═══════════════════════════════════════════════════════════════════════════
	//  MONTHLY VIEW
	// ═══════════════════════════════════════════════════════════════════════════
	function loadMonthly(){
		$main.html(skelCards(6)+`<div class="ap-two-col">${skelPanel()}${skelPanel()}</div>${skelPanel()}`);
		let p=2;
		const done=()=>{ if(--p===0) renderMonthly(state._md, state._hd); };
		frappe.call({
			method:"saral_hr.saral_hr.page.attendance_dashboard.attendance_dashboard.get_monthly_summary",
			args:{company:state.company, year:state.year, month:state.month, department:state.department},
			callback(r){ state._md=r.message; done(); }, error(){ state._md=null; done(); }
		});
		frappe.call({
			method:"saral_hr.saral_hr.page.attendance_dashboard.attendance_dashboard.get_holidays_for_month",
			args:{company:state.company, year:state.year, month:state.month},
			callback(r){ state._hd=r.message; done(); }, error(){ state._hd=null; done(); }
		});
	}

	function renderMonthly(d, hd){
		$main.empty();
		if(!d){ $main.html(`<div class="ap-empty">⚠️ Failed to load.</div>`); return; }
		setInfo(`<strong>${state.company}</strong> &nbsp;·&nbsp; ${d.month} ${d.year} &nbsp;·&nbsp; ${d.total_active} active employees &nbsp;·&nbsp; ${d.days_so_far} of ${d.total_days} days elapsed`);

		const ov = d.overall || {};

		// Top metric cards
		const nmColor = d.employees_never_marked>0 ? "#b91c1c" : "#16a34a";
		const $summary = $(`<div class="ap-monthly-summary"></div>`).appendTo($main);
		[
			{icon:"👥", label:"Total Active",   value:d.total_active,           sub:"Active employees",         bg:"#eff6ff",  border:"#bfdbfe",  valColor:"#1d4ed8"},
			{icon:"✔️", label:"Records Exist",  value:d.employees_with_records, sub:"Have records this month",  bg:"#f0fdf4",  border:"#86efac",  valColor:"#15803d"},
			{icon:"⚠️", label:"Never Marked",   value:d.employees_never_marked, sub:"No record at all",         bg:d.employees_never_marked>0?"#fef2f2":"#f0fdf4", border:d.employees_never_marked>0?"#fca5a5":"#86efac", valColor:nmColor},
		].forEach(s=>{
			$summary.append(`<div class="ap-ms-card" style="background:${s.bg};border-color:${s.border};">
				<div class="ap-ms-icon">${s.icon}</div>
				<div class="ap-ms-val" style="color:${s.valColor};">${s.value}</div>
				<div class="ap-ms-label">${s.label}</div>
				<div class="ap-ms-sub">${s.sub}</div>
			</div>`);
		});

		// Count cards
		const physPresent = ["Present","On Tour","Earned Comp Off"].reduce((s,k)=>s+(ov[k]||0),0);
		const onLeave     = ["Earned Leave","Casual Leave","Comp Off"].reduce((s,k)=>s+(ov[k]||0),0);
		const unpaid      = (ov["Absent"]||0)+(ov["LWP"]||0);
		const $cards = $(`<div class="ap-cards"></div>`).appendTo($main);
		[
			{icon:"🏢", val:physPresent,         label:"Physically Present", bg:"#15803d"},
			{icon:"🌴", val:onLeave,             label:"On Leave",           bg:"#7c3aed"},
			{icon:"🌗", val:ov["Half Day"]||0,   label:"Half Days",          bg:"#b45309"},
			{icon:"❌", val:unpaid,              label:"Absent / LWP",       bg:"#b91c1c"},
			{icon:"🎉", val:hd?hd.total:0,       label:"Holidays",           bg:"#0e7490"},
			{icon:"🔴", val:ov["LWP"]||0,        label:"LWP Only",           bg:"#991b1b"},
		].forEach(c=>$(`<div class="ap-card" style="background:${c.bg};">
			<div class="ap-card-icon">${c.icon}</div>
			<div class="ap-card-num" data-t="${c.val}">0</div>
			<div class="ap-card-label">${c.label}</div>
		</div>`).appendTo($cards));
		animNums($cards);

		// Daily trend + holidays side by side
		const $g = $(`<div class="ap-two-col"></div>`).appendTo($main);
		const $cp = $(`<div class="ap-panel"></div>`);
		$(`<div class="ap-panel-hd"><span class="ap-panel-title">📈 Daily Attendance Trend</span></div>`).appendTo($cp);
		renderChart($(`<div class="ap-chart"></div>`).appendTo($cp), d.day_trend);
		$g.append($cp);

		const $hp = $(`<div class="ap-panel"></div>`);
		$(`<div class="ap-panel-hd"><span class="ap-panel-title">🎉 Holidays this Month</span>${hd&&hd.total?`<span class="ap-badge" style="background:#0e7490;">${hd.total}</span>`:""}</div>`).appendTo($hp);
		if(!hd||!hd.holidays.length){
			$hp.append(`<div class="ap-empty">No holidays this month.</div>`);
		} else {
			hd.holidays.forEach(h=>$hp.append(`<div class="ap-hol-row">
				<div class="ap-hol-dot"></div>
				<div class="ap-hol-name">${h.description}</div>
				<div class="ap-hol-day">${h.day}</div>
				<div class="ap-hol-date">${frappe.datetime.str_to_user(h.date)}</div>
			</div>`));
		}
		$g.append($hp);

		// Full status breakdown
		const $bp = $(`<div class="ap-panel"></div>`).appendTo($main);
		$(`<div class="ap-panel-hd"><span class="ap-panel-title">📊 Full Status Breakdown</span></div>`).appendTo($bp);
		const $bw = $(`<div class="ap-bk-wrap"></div>`).appendTo($bp);
		if(!Object.keys(ov).length){ $bp.append(`<div class="ap-empty">No records yet.</div>`); }
		else {
			Object.entries(ov).sort((a,b)=>b[1]-a[1]).forEach(([st,cnt])=>{
				const m=STATUS_META[st]||{color:"#94a3b8",bg:"#f8fafc",border:"#e2e8f0",text:"#475569"};
				$bw.append(`<div class="ap-bk-chip" style="background:${m.bg};border-color:${m.border};">
					<span class="ap-bk-dot" style="background:${m.color};"></span>
					<span class="ap-bk-cnt" style="color:${m.color};">${cnt}</span>
					<span class="ap-bk-lbl" style="color:${m.text};">${st}</span>
				</div>`);
			});
		}

		// Per-employee attendance table
		const $ep = $(`<div class="ap-panel"></div>`).appendTo($main);
		$(`<div class="ap-panel-hd"><span class="ap-panel-title">👤 Employee-wise Attendance</span></div>`).appendTo($ep);
		const $ebody = $(`<div></div>`).appendTo($ep);
		const emps   = d.emp_attendance || [];
		const depts  = [...new Set(emps.map(e=>e.department).filter(Boolean))];
		if(depts.length>1){
			const $ds = $(`<div class="ap-dept-strip"></div>`).appendTo($ebody);
			const $all = $(`<span class="ap-dpill active">All</span>`).appendTo($ds);
			$all.on("click",()=>{ buildEmpRows(emps); $ds.find(".ap-dpill").removeClass("active"); $all.addClass("active"); });
			depts.forEach(dept=>{
				const $p=$(`<span class="ap-dpill">${dept}</span>`).appendTo($ds);
				$p.on("click",()=>{ buildEmpRows(emps.filter(e=>e.department===dept)); $ds.find(".ap-dpill").removeClass("active"); $p.addClass("active"); });
			});
		}
		const $sw  = buildSearch($ebody);
		const $el  = $(`<div></div>`).appendTo($ebody);
		function buildEmpRows(list){
			$el.empty();
			if(!list.length){ $el.html(`<div class="ap-empty">No employees.</div>`); return; }
			list.forEach(e=>{
				const pct=e.pct||0, bc=pct>=80?"#22c55e":pct>=60?"#f59e0b":"#ef4444";
				const ini=initials(e.name), hue=hueFor(e.employee||"A");
				const $r=$(`<div class="ap-emp-row">
					<div class="ap-av" style="background:hsl(${hue},62%,44%);">${ini}</div>
					<div class="ap-emp-info">
						<div class="ap-emp-name">${e.name}</div>
						<div class="ap-emp-meta">${e.department||"—"} · ${e.designation||"—"}</div>
					</div>
					<div style="text-align:right;min-width:110px;">
						<div style="display:flex;align-items:center;gap:5px;margin-bottom:2px;">
							<div class="ap-pct-bg"><div class="ap-pct-fill" style="width:${pct}%;background:${bc};"></div></div>
							<span style="font-size:11px;font-weight:700;color:${bc};min-width:30px;">${pct}%</span>
						</div>
						<div style="font-size:10px;color:var(--text-muted);">
							<span style="color:#16a34a;font-weight:700;">${e.present}</span> Present
							&nbsp;<span style="color:#dc2626;font-weight:700;">${e.absent}</span> Absent
						</div>
					</div>
				</div>`);
				$r.on("click",()=>openDrawer(e.employee, e.name, d.month, d.year));
				$el.append($r);
			});
		}
		buildEmpRows(emps);
		$sw.find(".ap-search").on("input",function(){
			const q=$(this).val().toLowerCase();
			buildEmpRows(q?emps.filter(e=>(e.name||"").toLowerCase().includes(q)):emps);
		});
	}

	// ═══════════════════════════════════════════════════════════════════════════
	//  YEARLY VIEW
	// ═══════════════════════════════════════════════════════════════════════════
	function loadYearly(){
		$main.html(skelCards(4)+skelPanel());
		let p=12, res={};
		MONTHS.forEach(m=>{
			frappe.call({
				method:"saral_hr.saral_hr.page.attendance_dashboard.attendance_dashboard.get_monthly_summary",
				args:{company:state.company, year:state.year, month:m, department:state.department},
				callback(r){ res[m]=r.message; if(--p===0) renderYearly(res); },
				error(){ res[m]=null; if(--p===0) renderYearly(res); }
			});
		});
	}

	function renderYearly(res){
		$main.empty();
		setInfo(`<strong>${state.company}</strong> &nbsp;·&nbsp; Year ${state.year}`);
		let tp=0, ta=0, tl=0, thd=0;
		MONTHS.forEach(m=>{
			const d=res[m]; if(!d) return;
			const ov=d.overall||{};
			tp  += ["Present","On Tour","Earned Comp Off"].reduce((s,k)=>s+(ov[k]||0),0);
			ta  += (ov["Absent"]||0)+(ov["LWP"]||0);
			tl  += ["Earned Leave","Casual Leave","Comp Off"].reduce((s,k)=>s+(ov[k]||0),0);
			thd += (ov["Half Day"]||0);
		});
		const fd = res[MONTHS[0]];
		const $cards = $(`<div class="ap-cards"></div>`).appendTo($main);
		[
			{icon:"👥", val:fd?fd.total_active:0, label:"Active",         bg:"#1e40af"},
			{icon:"🏢", val:tp,                   label:"Phys. Present",  bg:"#15803d"},
			{icon:"🌴", val:tl,                   label:"Leaves Taken",   bg:"#7c3aed"},
			{icon:"🌗", val:thd,                  label:"Half Days",      bg:"#b45309"},
			{icon:"❌", val:ta,                   label:"Absent / LWP",   bg:"#b91c1c"},
		].forEach(c=>$(`<div class="ap-card" style="background:${c.bg};">
			<div class="ap-card-icon">${c.icon}</div>
			<div class="ap-card-num" data-t="${c.val}">0</div>
			<div class="ap-card-label">${c.label}</div>
		</div>`).appendTo($cards));
		animNums($cards);

		const $p = $(`<div class="ap-panel"></div>`).appendTo($main);
		$(`<div class="ap-panel-hd"><span class="ap-panel-title">📅 ${state.year} — Month-wise Summary</span></div>`).appendTo($p);
		const $tbl = $(`<table class="ap-yr-tbl">
			<thead><tr>
				<th>Month</th>
				<th>Present</th>
				<th>On Leave</th>
				<th>Half Day</th>
				<th>Absent/LWP</th>
				<th>Holidays</th>
				<th>Attendance %</th>
			</tr></thead>
			<tbody></tbody>
		</table>`).appendTo($p);
		const $tb = $tbl.find("tbody");

		MONTHS.forEach(m=>{
			const d=res[m]; const ov=d?d.overall||{}:{};
			const pres  = ["Present","On Tour","Earned Comp Off"].reduce((s,k)=>s+(ov[k]||0),0);
			const leave = ["Earned Leave","Casual Leave","Comp Off"].reduce((s,k)=>s+(ov[k]||0),0);
			const hday  = ov["Half Day"]||0;
			const abs   = (ov["Absent"]||0)+(ov["LWP"]||0);
			const hol   = ov["Holiday"]||0;
			const mp    = d?d.total_days*(d.total_active||1):0;
			const pct   = mp>0 ? Math.round((pres/mp)*100) : 0;
			const bc    = pct>=80?"#22c55e":pct>=60?"#f59e0b":"#ef4444";
			const isCur = m===MONTHS[TODAY.getMonth()] && state.year===String(TODAY.getFullYear());
			const $tr   = $(`<tr ${isCur?'style="background:var(--primary-light);"':""}>
				<td style="font-weight:${isCur?"700":"600"};">${m}${isCur?` <span style="font-size:9px;background:var(--primary);color:#fff;padding:1px 6px;border-radius:6px;margin-left:4px;">Now</span>`:""}</td>
				<td style="color:#16a34a;font-weight:700;">${pres}</td>
				<td style="color:#7c3aed;font-weight:700;">${leave}</td>
				<td style="color:#b45309;font-weight:700;">${hday}</td>
				<td style="color:#dc2626;font-weight:700;">${abs}</td>
				<td style="color:#0e7490;font-weight:600;">${hol}</td>
				<td>
					<div style="display:flex;align-items:center;gap:7px;">
						<div class="ap-pct-bg" style="flex:1;">
							<div class="ap-pct-fill" style="width:${pct}%;background:${bc};"></div>
						</div>
						<span style="font-size:11px;font-weight:700;color:${bc};min-width:32px;">${pct}%</span>
					</div>
				</td>
			</tr>`);
			$tr.on("click",()=>{
				state.month=m; state.view="monthly";
				$vFi.find(".ap-vtab").removeClass("active");
				$vFi.find("[data-v='monthly']").addClass("active");
				renderPeriodFields(); loadMonthly();
			});
			$tb.append($tr);
		});
	}

	// ═══════════════════════════════════════════════════════════════════════════
	//  EMPLOYEE DETAIL DRAWER
	// ═══════════════════════════════════════════════════════════════════════════
	function openDrawer(employee, empName, month, year){
		const $ov = $(`<div class="ap-overlay"></div>`).appendTo("body");
		const $dr = $(`<div class="ap-drawer"></div>`).appendTo($ov);
		$dr.html(`<div class="ap-drawer-hd">
			<div>
				<div class="ap-drawer-title">Loading…</div>
				<div class="ap-drawer-sub">${month} ${year}</div>
			</div>
			<div class="ap-drawer-close">×</div>
		</div><div class="ap-drawer-body">${skelPanel()}</div>`);
		$dr.find(".ap-drawer-close").on("click",()=>$ov.remove());
		$ov.on("click",e=>{ if($(e.target).is($ov)) $ov.remove(); });

		frappe.call({
			method:"saral_hr.saral_hr.page.attendance_dashboard.attendance_dashboard.get_employee_monthly_detail",
			args:{employee, year:year||state.year, month:month||state.month},
			callback(r){
				const d = r.message;
				$dr.find(".ap-drawer-title").text(d.employee_name);
				$dr.find(".ap-drawer-sub").text(`${d.department} · ${d.designation} · ${d.month} ${d.year}`);
				const $b = $dr.find(".ap-drawer-body").empty();

				// Status summary chips
				const ss = d.status_summary || {};
				const $sr = $(`<div class="ap-ds-row"></div>`).appendTo($b);
				Object.entries(ss).sort((a,b)=>b[1]-a[1]).forEach(([st,cnt])=>{
					const m=STATUS_META[st]||{color:"#94a3b8",bg:"#f8fafc",border:"#e2e8f0",text:"#475569"};
					$sr.append(`<div class="ap-ds" style="background:${m.bg};border-color:${m.border};">
						<div class="ap-ds-val" style="color:${m.color};">${cnt}</div>
						<div class="ap-ds-lbl" style="color:${m.text};">${st}</div>
					</div>`);
				});

				$b.append(`<div style="font-size:10px;font-weight:800;color:var(--text-muted);text-transform:uppercase;margin:4px 0 10px;letter-spacing:.5px;">Attendance Calendar</div>`);

				// Heatmap calendar
				const $cal = $(`<div class="ap-cal"></div>`).appendTo($b);
				["Su","Mo","Tu","We","Th","Fr","Sa"].forEach(l=>$cal.append(`<div class="ap-cal-lbl">${l}</div>`));
				const fd = new Date(d.year, d.month_num-1, 1).getDay();
				for(let i=0;i<fd;i++) $cal.append(`<div></div>`);
				const tod = frappe.datetime.get_today();
				d.days.forEach(day=>{
					const m = STATUS_META[day.status]||{color:"#d1d5db"};
					const isNR  = day.status==="Not Marked";
					const isTod = day.date===tod;
					const $c = $(`<div class="ap-cal-cell ${isTod?"ap-cal-today":""}" style="background:${isNR?"var(--subtle-fg)":m.color};color:${isNR?"var(--text-muted)":"#fff"};">${day.day}</div>`);
					$c.on("mouseenter",e=>tip(`${frappe.datetime.str_to_user(day.date)} · ${day.status}`,e))
					  .on("mousemove",e=>tip(`${frappe.datetime.str_to_user(day.date)} · ${day.status}`,e))
					  .on("mouseleave",hideTip);
					$cal.append($c);
				});

				// Legend
				const seen = [...new Set(d.days.map(x=>x.status))].filter(s=>s!=="Not Marked");
				const $leg = $(`<div style="display:flex;flex-wrap:wrap;gap:7px;margin-top:12px;"></div>`).appendTo($b);
				seen.forEach(st=>{
					const m=STATUS_META[st]||{color:"#94a3b8"};
					$leg.append(`<div style="display:flex;align-items:center;gap:4px;font-size:11px;color:var(--text-muted);"><div style="width:9px;height:9px;border-radius:2px;background:${m.color};"></div>${st}</div>`);
				});
			}
		});
	}

	// ═══════════════════════════════════════════════════════════════════════════
	//  HELPERS
	// ═══════════════════════════════════════════════════════════════════════════
	function renderChart($container, trend){
		const mx = Math.max(...trend.map(d=>d.present+d.absent), 1);
		const $bars = $(`<div class="ap-bars"></div>`).appendTo($container);
		trend.forEach(d=>{
			const ph = Math.round((d.present/mx)*84);
			const ah = Math.round((d.absent/mx)*84);
			const txt = `${frappe.datetime.str_to_user(d.date)}: ${d.present} present, ${d.absent} absent`;
			const $c = $(`<div class="ap-bc"></div>`);
			if(ah>0) $c.append($(`<div class="ap-bs" style="height:${ah}px;background:#ef4444;"></div>`).on("mouseenter",e=>tip(txt,e)).on("mousemove",e=>tip(txt,e)).on("mouseleave",hideTip));
			if(ph>0) $c.append($(`<div class="ap-bs" style="height:${ph}px;background:#22c55e;"></div>`).on("mouseenter",e=>tip(txt,e)).on("mousemove",e=>tip(txt,e)).on("mouseleave",hideTip));
			$c.append(`<div class="ap-bd">${d.day}</div>`);
			$bars.append($c);
		});
		$(`<div class="ap-chart-leg">
			<div class="ap-cl-item"><div class="ap-cl-dot" style="background:#22c55e;"></div>Present (incl. ECO, On Tour)</div>
			<div class="ap-cl-item"><div class="ap-cl-dot" style="background:#ef4444;"></div>Absent / LWP</div>
		</div>`).appendTo($container);
	}

	function buildSearch($container){
		return $(`<div class="ap-search-wrap">
			<svg class="ap-search-ico" width="13" height="13" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/></svg>
			<input type="text" class="ap-search" placeholder="Search by name…">
		</div>`).appendTo($container);
	}

	function initials(name){ return (name||"?").split(" ").map(w=>w[0]).join("").toUpperCase().slice(0,2); }
	function hueFor(str)   { return (str||"A").charCodeAt(0)*47%360; }

	function animNums($ctx){
		$ctx.find(".ap-card-num[data-t]").each(function(){
			const $el=$(this), t=parseInt($el.data("t"))||0;
			if(!t){ $el.text("0"); return; }
			const inc=Math.ceil(t/25); let cur=0;
			const iv=setInterval(()=>{ cur=Math.min(cur+inc,t); $el.text(cur); if(cur>=t) clearInterval(iv); }, 22);
		});
	}

	function skelCards(n=6){
		return `<div class="ap-cards">${Array(n).fill(0).map(()=>`<div class="ap-card" style="background:var(--subtle-fg);box-shadow:none;"><div class="ap-sk" style="height:14px;width:14px;border-radius:50%;margin-bottom:6px;"></div><div class="ap-sk" style="height:26px;width:44px;margin-bottom:3px;"></div><div class="ap-sk" style="height:8px;width:58px;"></div></div>`).join("")}</div>`;
	}
	function skelPanel(){
		return `<div class="ap-panel" style="margin-bottom:14px;"><div class="ap-panel-hd"><div class="ap-sk" style="width:130px;height:13px;"></div></div><div style="padding:14px;">${[1,2,3].map(()=>`<div class="ap-sk" style="height:38px;margin-bottom:7px;border-radius:7px;"></div>`).join("")}</div></div>`;
	}
};