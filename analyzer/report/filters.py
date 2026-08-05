"""Filter bar JavaScript and report navigation."""


def _build_filter_js(visible_owners, show_unassigned):
    """生成筛选功能的 JavaScript 代码（人员 + 排期状态）。"""
    owner_keys = list(visible_owners)
    count_keys = ['all'] + owner_keys + (['unassigned'] if show_unassigned else [])
    counts_init = ', '.join([f'{k}: 0' for k in count_keys])
    counts_checks = '\n'.join([
        f"                    if (ownerList.includes('{k}')) counts.{k}++;"
        for k in owner_keys
    ])
    remove_class_parts = [f"'active-{k}'" for k in owner_keys]
    if show_unassigned:
        remove_class_parts.append("'active-unassigned'")
    remove_class_parts.append("'active'")
    remove_owner_classes = ', '.join(remove_class_parts)

    if show_unassigned:
        count_loop = """
                if (!owners) {
                    counts.unassigned++;
                } else {
                    const ownerList = owners.split(',');
""" + counts_checks + """
                }"""
    else:
        count_loop = """
                if (owners) {
                    const ownerList = owners.split(',');
""" + counts_checks + """
                }"""

    return """
    <script>
        let currentOwnerFilter = 'all';
        let currentScheduleFilter = 'all';
        let currentSort = 'key-desc';
        let currentProjectFilter = null;

        const URL_DEFAULTS = { sort: 'key-desc', schedule: 'all', owner: 'all' };
        const VALID_SORTS = ['key-desc', 'key-asc', 'count-desc', 'count-asc'];
        const VALID_SCHEDULES = ['all', 'scheduled', 'unscheduled', 'scheduled-processed'];

        function parseProjectParam(value) {
            if (!value) return null;
            const keys = value.split(',').map(k => k.trim().toUpperCase()).filter(Boolean);
            return keys.length ? new Set(keys) : null;
        }

        function matchesProjectFilter(sectionKey) {
            if (!currentProjectFilter) return true;
            return currentProjectFilter.has((sectionKey || '').toUpperCase());
        }

        function syncUrlParams() {
            const params = new URLSearchParams(window.location.search);
            if (currentSort === URL_DEFAULTS.sort) params.delete('sort');
            else params.set('sort', currentSort);
            if (currentScheduleFilter === URL_DEFAULTS.schedule) params.delete('schedule');
            else params.set('schedule', currentScheduleFilter);
            if (currentOwnerFilter === URL_DEFAULTS.owner) params.delete('owner');
            else params.set('owner', currentOwnerFilter);
            if (!currentProjectFilter) params.delete('project');
            else params.set('project', [...currentProjectFilter].join(','));
            const qs = params.toString();
            const newUrl = qs ? `${window.location.pathname}?${qs}` : window.location.pathname;
            history.replaceState(null, '', newUrl);
        }

        function matchesScheduleFilter(processed, scheduled) {
            if (currentScheduleFilter === 'all') {
                return !processed;
            }
            if (currentScheduleFilter === 'scheduled') {
                return scheduled && !processed;
            }
            if (currentScheduleFilter === 'unscheduled') {
                return !scheduled && !processed;
            }
            if (currentScheduleFilter === 'scheduled-processed') {
                return scheduled && processed;
            }
            return false;
        }

        function updateCounts() {
            const allItems = document.querySelectorAll('li.item-row');
            const counts = { """ + counts_init + """ };
            allItems.forEach(li => {
                const scheduled = li.getAttribute('data-scheduled') === 'true';
                const processed = li.getAttribute('data-processed') === 'true';
                if (!matchesScheduleFilter(processed, scheduled)) return;
                counts.all++;
                const owners = li.getAttribute('data-owners');
""" + count_loop + """
            });
            for (const [key, count] of Object.entries(counts)) {
                const el = document.getElementById('count-' + key);
                if (el) el.textContent = count || '';
            }
        }

        function applyFilters() {
            const allItems = document.querySelectorAll('li.item-row');
            allItems.forEach(li => {
                const owners = li.getAttribute('data-owners');
                const scheduled = li.getAttribute('data-scheduled') === 'true';
                const processed = li.getAttribute('data-processed') === 'true';

                let showOwner = false;
                if (currentOwnerFilter === 'all') {
                    showOwner = true;
                } else if (currentOwnerFilter === 'unassigned') {
                    showOwner = !owners;
                } else {
                    showOwner = owners && owners.split(',').includes(currentOwnerFilter);
                }

                const showSchedule = matchesScheduleFilter(processed, scheduled);
                li.style.display = showOwner && showSchedule ? '' : 'none';
            });

            document.querySelectorAll('.task-section').forEach(section => {
                const sectionKey = section.getAttribute('data-key');
                if (!matchesProjectFilter(sectionKey)) {
                    section.style.display = 'none';
                    return;
                }
                const visibleItems = section.querySelectorAll('li.item-row:not([style*="display: none"])');
                section.style.display = visibleItems.length > 0 ? '' : 'none';
            });
            updateCounts();
        }

        function applyOwnerFilterUI(filter) {
            document.querySelectorAll('.owner-bar .filter-btn').forEach(btn => {
                btn.classList.remove(""" + remove_owner_classes + """);
            });
            const activeBtn = document.querySelector(`.owner-bar .filter-btn[data-filter="${filter}"]`);
            if (activeBtn) {
                if (filter === 'all') {
                    activeBtn.classList.add('active');
                } else {
                    activeBtn.classList.add('active-' + filter);
                }
            }
        }

        function applyScheduleFilterUI(filter) {
            document.querySelectorAll('.schedule-bar .filter-btn').forEach(btn => {
                btn.classList.remove(
                    'active', 'active-scheduled', 'active-unscheduled', 'active-scheduled-processed'
                );
            });
            const activeBtn = document.querySelector(`.schedule-bar .filter-btn[data-schedule="${filter}"]`);
            if (activeBtn) {
                if (filter === 'all') {
                    activeBtn.classList.add('active');
                } else if (filter === 'scheduled') {
                    activeBtn.classList.add('active-scheduled');
                } else if (filter === 'scheduled-processed') {
                    activeBtn.classList.add('active-scheduled-processed');
                } else {
                    activeBtn.classList.add('active-unscheduled');
                }
            }
        }

        function applySortUI(sortBy) {
            document.querySelectorAll('.sort-btn').forEach(btn => btn.classList.remove('active'));
            const activeBtn = document.querySelector(`.sort-btn[data-sort="${sortBy}"]`);
            if (activeBtn) activeBtn.classList.add('active');
        }

        function filterItems(filter, options = {}) {
            const btn = document.querySelector(`.owner-bar .filter-btn[data-filter="${filter}"]`);
            if (!btn) return;
            currentOwnerFilter = filter;
            applyOwnerFilterUI(filter);
            if (!options.skipApply) {
                applyFilters();
                if (!options.skipUrl) syncUrlParams();
            }
        }

        function filterSchedule(filter, options = {}) {
            if (!VALID_SCHEDULES.includes(filter)) return;
            currentScheduleFilter = filter;
            applyScheduleFilterUI(filter);
            if (!options.skipApply) {
                applyFilters();
                if (!options.skipUrl) syncUrlParams();
            }
        }

        function sortSections(sortBy, options = {}) {
            if (!VALID_SORTS.includes(sortBy)) return;
            currentSort = sortBy;
            applySortUI(sortBy);

            const container = document.getElementById('task-container');
            if (!container) return;
            const sections = Array.from(container.querySelectorAll('.task-section'));

            sections.sort((a, b) => {
                const keyA = a.getAttribute('data-key') || '';
                const keyB = b.getAttribute('data-key') || '';
                const numA = parseInt(keyA.replace(/[^0-9]/g, '')) || 0;
                const numB = parseInt(keyB.replace(/[^0-9]/g, '')) || 0;
                const countA = parseInt(a.getAttribute('data-count')) || 0;
                const countB = parseInt(b.getAttribute('data-count')) || 0;

                switch (sortBy) {
                    case 'key-desc': return numB - numA;
                    case 'key-asc': return numA - numB;
                    case 'count-desc': return countB - countA || numB - numA;
                    case 'count-asc': return countA - countB || numA - numB;
                    default: return numB - numA;
                }
            });

            sections.forEach(section => container.appendChild(section));
            if (!options.skipUrl) syncUrlParams();
        }

        function initFromUrl() {
            const params = new URLSearchParams(window.location.search);
            currentProjectFilter = parseProjectParam(params.get('project'));

            const schedule = params.get('schedule');
            if (schedule && VALID_SCHEDULES.includes(schedule)) {
                filterSchedule(schedule, { skipApply: true, skipUrl: true });
            } else {
                applyScheduleFilterUI(currentScheduleFilter);
            }

            const owner = params.get('owner');
            if (owner) {
                const ownerBtn = document.querySelector(`.owner-bar .filter-btn[data-filter="${owner}"]`);
                if (ownerBtn) {
                    currentOwnerFilter = owner;
                    applyOwnerFilterUI(owner);
                } else {
                    applyOwnerFilterUI(currentOwnerFilter);
                }
            } else {
                applyOwnerFilterUI(currentOwnerFilter);
            }

            const sort = params.get('sort');
            if (sort && VALID_SORTS.includes(sort)) {
                sortSections(sort, { skipUrl: true });
            } else {
                applySortUI(currentSort);
            }

            applyFilters();
            syncUrlParams();
        }

        initFromUrl();
    </script>"""


def _build_report_nav(nav_links, current_label):
    """报告间切换导航（如 Q3 ↔ Q2）。"""
    if not nav_links or len(nav_links) < 2:
        return ''
    items = []
    for link in nav_links:
        label = link.get('label', '')
        href = link.get('href', './')
        if label == current_label:
            items.append(f'<span class="nav-current">{label}</span>')
        else:
            items.append(f'<a class="nav-link" href="{href}">{label}</a>')
    return f'<nav class="report-nav" aria-label="季度切换">{"".join(items)}</nav>'
