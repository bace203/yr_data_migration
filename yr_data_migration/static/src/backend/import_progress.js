/** @odoo-module */
// Progress bar of the fastmag import screen: polls the import while it runs.
import { Component, onWillUnmount, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { standardWidgetProps } from "@web/views/widgets/standard_widget_props";

export class ImportProgress extends Component {
    static template = "yr_data_migration.ImportProgress";
    static props = { ...standardWidgetProps };

    setup() {
        this.orm = useService("orm");
        this.state = useState({ info: null });
        this.timer = setInterval(() => this.poll(), 1000);
        onWillUnmount(() => clearInterval(this.timer));
    }

    async poll() {
        const record = this.props.record;
        if (!record.resId || record.data.state !== "draft" || this.busy) {
            return;
        }
        this.busy = true;
        try {
            const info = await this.orm.call("yr.migration.import", "get_progress", [[record.resId]]);
            this.state.info = info && info.state === "running" ? info : null;
        } catch {
            // the screen was closed or the record is gone
        } finally {
            this.busy = false;
        }
    }

    get percent() {
        return Math.round(this.state.info?.progress || 0);
    }
}

registry.category("view_widgets").add("yr_import_progress", { component: ImportProgress });
