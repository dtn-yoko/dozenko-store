const api = (path, opts = {}) => fetch(path, opts).then(async (r) => {
  const data = await r.json().catch(() => ({}));
  if (!r.ok) {
    throw new Error(data.error || `HTTP ${r.status}`);
  }
  return data;
});

const byId = (id) => document.getElementById(id);

function money(v) {
  return Number(v || 0).toLocaleString("vi-VN") + "d";
}

function esc(v) {
  if (v === null || v === undefined) return "";
  return String(v)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function bindTabs() {
  document.querySelectorAll(".tab-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".tab-btn").forEach((b) => b.classList.remove("active"));
      document.querySelectorAll(".panel").forEach((p) => p.classList.remove("active"));
      btn.classList.add("active");
      byId(`panel-${btn.dataset.tab}`).classList.add("active");
    });
  });
}

async function loadProducts() {
  const products = await api("/api/products");
  byId("products-body").innerHTML = products.map((p) => `
    <tr>
      <td>${p.id}</td>
      <td>${esc(p.name)}</td>
      <td>${esc(p.type)}</td>
      <td>${money(p.price)}</td>
      <td>${p.quantity ?? "N/A"}</td>
      <td>
        <div class="actions">
          <button class="btn btn-alt" data-edit-product="${p.id}">Sua</button>
          <button class="btn btn-danger" data-del-product="${p.id}">Xoa</button>
        </div>
      </td>
    </tr>
  `).join("");

  document.querySelectorAll("[data-edit-product]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const id = Number(btn.dataset.editProduct);
      const p = products.find((x) => x.id === id);
      if (!p) return;
      const name = prompt("Ten san pham", p.name);
      if (!name) return;
      const type = (prompt("Loai (physical/digital/service)", p.type) || p.type).toLowerCase();
      const price = prompt("Gia", p.price);
      const quantity = type === "physical" ? prompt("Ton kho", p.quantity ?? "0") : "";
      const description = prompt("Mo ta", p.description || "") || "";

      try {
        await api(`/api/products/${id}`, {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ name, type, price, quantity, description })
        });
        await loadAll();
      } catch (e) {
        alert(e.message);
      }
    });
  });

  document.querySelectorAll("[data-del-product]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const id = Number(btn.dataset.delProduct);
      if (!confirm("Xoa san pham nay?")) return;
      try {
        await api(`/api/products/${id}`, { method: "DELETE" });
        await loadAll();
      } catch (e) {
        alert(e.message);
      }
    });
  });
}

async function loadCustomers() {
  const customers = await api("/api/customers");
  byId("customers-body").innerHTML = customers.map((c) => `
    <tr>
      <td>${c.id}</td>
      <td>${esc(c.name)}</td>
      <td>${esc(c.phone)}</td>
      <td>${esc(c.zalo || "")}</td>
      <td>${esc(c.signup_date || "")}</td>
      <td>
        <div class="actions">
          <button class="btn btn-alt" data-edit-customer="${c.id}">Sua</button>
          <button class="btn btn-danger" data-del-customer="${c.id}">Xoa</button>
        </div>
      </td>
    </tr>
  `).join("");

  document.querySelectorAll("[data-edit-customer]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const id = Number(btn.dataset.editCustomer);
      const c = customers.find((x) => x.id === id);
      if (!c) return;
      const name = prompt("Ten", c.name);
      const phone = prompt("Phone", c.phone);
      const zalo = prompt("Zalo", c.zalo || "");
      if (!name || !phone) return;
      try {
        await api(`/api/customers/${id}`, {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ name, phone, zalo })
        });
        await loadAll();
      } catch (e) {
        alert(e.message);
      }
    });
  });

  document.querySelectorAll("[data-del-customer]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const id = Number(btn.dataset.delCustomer);
      if (!confirm("Xoa khach hang nay?")) return;
      try {
        await api(`/api/customers/${id}`, { method: "DELETE" });
        await loadAll();
      } catch (e) {
        alert(e.message);
      }
    });
  });
}

async function loadOrders() {
  const orders = await api("/api/orders");
  byId("orders-body").innerHTML = orders.map((o) => `
    <tr>
      <td>${o.id}</td>
      <td>${esc(o.customer_name)}<br><small>${esc(o.customer_phone || "")}</small></td>
      <td>${esc(o.product_name)}</td>
      <td>${money(o.amount)}</td>
      <td><span class="status ${esc(o.status)}">${esc(o.status)}</span></td>
      <td>${esc(o.order_date || "")}</td>
      <td>
        <div class="actions">
          <button class="btn btn-alt" data-edit-order="${o.id}">Sua</button>
          <button class="btn btn-danger" data-del-order="${o.id}">Xoa</button>
        </div>
      </td>
    </tr>
  `).join("");

  document.querySelectorAll("[data-edit-order]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const id = Number(btn.dataset.editOrder);
      const o = orders.find((x) => x.id === id);
      if (!o) return;
      const amount = prompt("So tien", o.amount);
      const status = (prompt("Trang thai (pending/success/failed/cancelled)", o.status) || o.status).toLowerCase();
      try {
        await api(`/api/orders/${id}`, {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ amount, status })
        });
        await loadAll();
      } catch (e) {
        alert(e.message);
      }
    });
  });

  document.querySelectorAll("[data-del-order]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const id = Number(btn.dataset.delOrder);
      if (!confirm("Xoa don hang nay?")) return;
      try {
        await api(`/api/orders/${id}`, { method: "DELETE" });
        await loadAll();
      } catch (e) {
        alert(e.message);
      }
    });
  });
}

async function loadAll() {
  await Promise.all([loadProducts(), loadCustomers(), loadOrders()]);
}

function bindAddButtons() {
  byId("add-product").addEventListener("click", async () => {
    const name = prompt("Ten san pham");
    if (!name) return;
    const type = (prompt("Loai (physical/digital/service)", "physical") || "physical").toLowerCase();
    const price = prompt("Gia", "300000");
    const quantity = type === "physical" ? prompt("Ton kho", "10") : "";
    const description = prompt("Mo ta", "") || "";
    try {
      await api("/api/products", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name, type, price, quantity, description })
      });
      await loadAll();
    } catch (e) {
      alert(e.message);
    }
  });

  byId("add-customer").addEventListener("click", async () => {
    const name = prompt("Ten khach hang");
    const phone = prompt("Phone");
    if (!name || !phone) return;
    const zalo = prompt("Zalo", phone) || phone;
    try {
      await api("/api/customers", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name, phone, zalo })
      });
      await loadAll();
    } catch (e) {
      alert(e.message);
    }
  });

  byId("add-order").addEventListener("click", async () => {
    try {
      const [customers, products] = await Promise.all([
        api("/api/customers"),
        api("/api/products")
      ]);
      if (!customers.length || !products.length) {
        alert("Can co it nhat 1 khach hang va 1 san pham.");
        return;
      }

      const customerId = prompt(
        `Nhap customer_id:\n${customers.map((c) => `${c.id} - ${c.name} (${c.phone})`).join("\n")}`,
        customers[0].id
      );
      const productId = prompt(
        `Nhap product_id:\n${products.map((p) => `${p.id} - ${p.name}`).join("\n")}`,
        products[0].id
      );
      const amount = prompt("So tien", products[0].price || "300000");
      const status = (prompt("Trang thai", "pending") || "pending").toLowerCase();
      const quantity = prompt("So luong tru ton kho", "1");

      await api("/api/orders", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          customer_id: Number(customerId),
          product_id: Number(productId),
          amount: Number(amount),
          status,
          quantity: Number(quantity || 1)
        })
      });

      await loadAll();
    } catch (e) {
      alert(e.message);
    }
  });
}

document.addEventListener("DOMContentLoaded", async () => {
  bindTabs();
  bindAddButtons();
  try {
    await loadAll();
  } catch (e) {
    alert(`Khong tai duoc du lieu: ${e.message}`);
  }
});