    // GameDock: list view, one row per game with its status
    function renderListView(games) {
        const gameGrid = $('#gameGrid');
        gameGrid.empty();

        const table = $(`<table class="table table-hover align-middle library-list mb-0">
            <thead>
                <tr>
                    <th></th>
                    <th>Name</th>
                    <th class="d-none d-md-table-cell">Title ID</th>
                    <th>Type</th>
                    <th class="d-none d-sm-table-cell">Version</th>
                    <th>Status</th>
                </tr>
            </thead>
            <tbody></tbody>
        </table>`);

        games.forEach(game => {
            const href = `/title/${game.title_id}`;
            const icon = game.iconUrl
                ? $('<img class="library-list-icon" loading="lazy" alt="">').attr('src', game.iconUrl)
                : $('<div class="library-list-icon"></div>');

            const name = $('<td></td>').append(
                $('<a class="library-list-name"></a>').attr('href', href).text(game.title_id_name || game.name));
            if (game.app_type === 'DLC') {
                name.append($('<div class="small text-body-secondary"></div>').text(game.name));
            }

            const owned = (game.version || []).filter(v => v.owned).sort((a, b) => b.version - a.version)[0];
            const version = owned ? (owned.display_version || `v${owned.version}`) : '—';
            const typeClass = game.owned === false ? 'text-bg-warning' : 'text-bg-info';

            const status = $('<td class="text-nowrap"></td>');
            if (game.has_latest_version !== undefined) {
                status.append(listStatusIcon(game.has_latest_version, 'bi-check-circle-fill', 'bi-arrow-down-circle',
                    game.has_latest_version ? 'Latest update owned' : 'Update missing'));
            }
            if (game.has_all_dlcs !== undefined) {
                status.append(listStatusIcon(game.has_all_dlcs, 'bi-box-seam-fill', 'bi-box-seam',
                    game.has_all_dlcs ? 'Every DLC owned' : 'DLC missing'));
            }

            // The whole row opens the game, like a card does
            const row = $('<tr class="library-list-row"></tr>').on('click', e => {
                if (!$(e.target).closest('a').length) {
                    window.location.href = href;
                }
            });
            row.append(
                $('<td class="library-list-icon-cell"></td>').append(icon),
                name,
                $('<td class="d-none d-md-table-cell font-monospace small"></td>').text(game.title_id || ''),
                $('<td></td>').append($(`<span class="badge rounded-pill ${typeClass}"></span>`).text(game.app_type)),
                $('<td class="d-none d-sm-table-cell"></td>').text(version),
                status,
            );
            table.find('tbody').append(row);
        });

        gameGrid.append($('<div class="col-12"></div>').append($('<div class="table-responsive"></div>').append(table)));
    }

    function listStatusIcon(ok, okIcon, missingIcon, label) {
        return $('<i class="bi me-2"></i>')
            .addClass(ok ? `${okIcon} text-success` : `${missingIcon} text-warning`)
            .attr('title', label)
            .attr('aria-label', label);
    }

