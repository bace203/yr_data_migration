/** @odoo-module */
// Many files for the import queue: sent one at a time (a request per file, so a big batch never overflows the
// server's upload limit), each with its own status.
import { Component, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { x2ManyCommands } from "@web/core/orm_service";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

export class FileQueueField extends Component {
    static template = "yr_data_migration.FileQueueField";
    static props = { ...standardFieldProps };

    setup() {
        this.state = useState({ sending: [] });
    }

    get files() {
        return this.props.record.data[this.props.name].records.map((record) => ({
            id: record.resId,
            name: record.data.display_name || record.data.name,
        }));
    }

    async onChange(ev) {
        const files = [...ev.target.files];
        ev.target.value = null;
        for (const file of files) {
            const entry = { name: file.name, error: "" };
            this.state.sending.push(entry);
            try {
                const data = new FormData();
                data.append("csrf_token", odoo.csrf_token);
                data.append("ufile", file);
                data.append("model", "yr.migration.import");
                data.append("id", 0);
                const response = await fetch("/web/binary/upload_attachment", { method: "POST", body: data });
                const text = await response.text();
                let parsed;
                try {
                    parsed = JSON.parse(text);
                } catch {
                    throw new Error(
                        `Le serveur a refusé l'envoi (code ${response.status}${
                            response.status === 413 ? " : fichier trop gros pour le serveur web" : ""
                        }).`
                    );
                }
                if (!parsed[0] || parsed[0].error) {
                    throw new Error(parsed[0]?.error || "Envoi impossible.");
                }
                await this.props.record.update({
                    [this.props.name]: [x2ManyCommands.link(parsed[0].id)],
                });
                this.state.sending.splice(this.state.sending.indexOf(entry), 1);
            } catch (error) {
                entry.error = error.message;
            }
        }
    }

    remove(id) {
        this.props.record.update({ [this.props.name]: [x2ManyCommands.unlink(id)] });
    }

    dismiss(entry) {
        this.state.sending.splice(this.state.sending.indexOf(entry), 1);
    }
}

registry.category("fields").add("yr_file_queue", {
    component: FileQueueField,
    supportedTypes: ["many2many"],
    isEmpty: () => false,
    relatedFields: [{ name: "name", type: "char" }],
});
