/** Seller (« Vendeur ») chosen before payment; the cashier stays the connected user / employee. */
import { _t } from "@web/core/l10n/translation";
import { patch } from "@web/core/utils/patch";
import { PosStore } from "@point_of_sale/app/store/pos_store";
import { PosOrder } from "@point_of_sale/app/models/pos_order";
import { ControlButtons } from "@point_of_sale/app/screens/product_screen/control_buttons/control_buttons";
import { SelectionPopup } from "@point_of_sale/app/utils/input_popups/selection_popup";
import { makeAwaitable } from "@point_of_sale/app/store/make_awaitable_dialog";

const NONE = -1;

patch(PosOrder.prototype, {
    yrSellerName() {
        const seller = (this.config.yr_seller_data || []).find((s) => s.id === this.yr_seller_ref);
        return seller ? seller.name : "";
    },
    export_for_printing() {
        const result = super.export_for_printing(...arguments);
        const seller = this.yrSellerName();
        if (seller) {
            result.headerData = { ...(result.headerData || {}), yr_seller: seller };
        }
        return result;
    },
});

patch(PosStore.prototype, {
    get yrSellers() {
        return this.config.yr_seller_mode === "none" ? [] : this.config.yr_seller_data || [];
    },
    /** Opens the list of sellers; returns false if the cashier closed it without choosing. */
    async yrSelectSeller(order = this.get_order()) {
        const sellers = this.yrSellers;
        if (!order || !sellers.length) {
            return true;
        }
        const list = sellers.map((s) => ({
            id: s.id,
            label: s.name,
            isSelected: s.id === order.yr_seller_ref,
            item: s.id,
        }));
        if (this.config.yr_seller_mode === "optional") {
            list.push({ id: NONE, label: _t("Pas de vendeur"), isSelected: false, item: NONE });
        }
        const payload = await makeAwaitable(this.dialog, SelectionPopup, {
            title: _t("Qui a servi le client ?"),
            list,
        });
        if (payload === undefined) {
            return false;
        }
        order.yr_seller_ref = payload === NONE ? 0 : payload;
        order.uiState.yrSellerAsked = true;
        return true;
    },
    async pay() {
        const order = this.get_order();
        if (order && this.yrSellers.length && order.canPay()) {
            const missing = !order.yr_seller_ref;
            const needed = this.config.yr_seller_mode === "required" ? missing : missing && !order.uiState?.yrSellerAsked;
            if (needed && !(await this.yrSelectSeller(order))) {
                return;
            }
            if (this.config.yr_seller_mode === "required" && !order.yr_seller_ref) {
                return;
            }
        }
        return super.pay(...arguments);
    },
});

patch(ControlButtons.prototype, {
    get yrSellerLabel() {
        return this.pos.get_order()?.yrSellerName() || _t("Vendeur");
    },
    async clickYrSeller() {
        await this.pos.yrSelectSeller();
        this.props.close?.();
    },
});
