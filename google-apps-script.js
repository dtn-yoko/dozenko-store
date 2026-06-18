/**
 * DOZENKO — Google Apps Script v2
 * Hoạt động như PROXY:
 * 1. Nhận đơn hàng từ website
 * 2. Ghi vào Google Sheets
 * 3. Gửi đơn lên CRM (Flask)
 *
 * Dán code này vào Google Apps Script:
 * https://script.google.com/
 * Deploy > Web App > Execute as: Me, Who has access: Anyone
 */

// ==== CẬP NHẬT URL TUNNEL MỖI KHI KHỞI ĐỘNG LẠI ====
const CRM_BASE_URL = 'https://splendid-fireant-67.loca.lt';

function doPost(e) {
  try {
    const data = JSON.parse(e.postData.contents);
    
    // 1. Ghi vào Google Sheets
    try {
      const sheet = SpreadsheetApp.getActiveSpreadsheet().getActiveSheet();
      if (sheet.getLastRow() === 0) {
        sheet.appendRow(['Timestamp', 'Name', 'Email', 'Phone', 'Quantity', 'Price', 'Colors', 'Address', 'Notes', 'Status']);
        sheet.getRange(1, 1, 1, 10).setBackground('#2A4E7C').setFontColor('#FFFFFF').setFontWeight('bold');
      }
      sheet.appendRow([
        data.timestamp || new Date().toLocaleString('vi-VN'),
        data.name || '',
        data.email || '',
        data.phone || '',
        data.quantity || '',
        data.price || '',
        data.colors || '',
        data.address || '',
        data.notes || '',
        'pending'
      ]);
    } catch(sheetErr) {
      Logger.log('Sheet error: ' + sheetErr);
    }
    
    // 2. Gửi đơn vào CRM Flask
    let crmResult = null;
    try {
      const name = data.name || '';
      const phone = data.phone || '';
      const headers = {
        'Content-Type': 'application/json',
        'bypass-tunnel-reminder': '1'
      };
      
      // Tạo khách hàng
      UrlFetchApp.fetch(CRM_BASE_URL + '/api/customers', {
        method: 'post',
        contentType: 'application/json',
        headers: headers,
        payload: JSON.stringify({ name: name, phone: phone, zalo: phone }),
        muteHttpExceptions: true
      });
      
      // Lấy customer ID
      const custResp = UrlFetchApp.fetch(CRM_BASE_URL + '/api/customers', { headers: headers, muteHttpExceptions: true });
      const customers = JSON.parse(custResp.getContentText());
      const customer = customers.find(c => c.phone === phone || c.name === name);
      
      // Lấy product đầu tiên
      const prodResp = UrlFetchApp.fetch(CRM_BASE_URL + '/api/products', { headers: headers, muteHttpExceptions: true });
      const products = JSON.parse(prodResp.getContentText());
      const product = products[0];
      
      // Tạo đơn hàng
      if (customer && product) {
        const priceMap = { '1': 300000, '2': 500000, '3': 700000, '4': 840000 };
        const qty = parseInt(data.quantity) || 1;
        const amount = priceMap[qty] || 300000;
        
        const orderResp = UrlFetchApp.fetch(CRM_BASE_URL + '/api/orders', {
          method: 'post',
          contentType: 'application/json',
          headers: headers,
          payload: JSON.stringify({
            customer_id: customer.id,
            product_id: product.id,
            amount: amount,
            status: 'pending'
          }),
          muteHttpExceptions: true
        });
        crmResult = JSON.parse(orderResp.getContentText());
      }
    } catch(crmErr) {
      Logger.log('CRM error: ' + crmErr);
      crmResult = { error: crmErr.toString() };
    }
    
    return ContentService
      .createTextOutput(JSON.stringify({ success: true, crm: crmResult }))
      .setMimeType(ContentService.MimeType.JSON);

  } catch (err) {
    return ContentService
      .createTextOutput(JSON.stringify({ success: false, error: err.toString() }))
      .setMimeType(ContentService.MimeType.JSON);
  }
}

function testSetup() {
  Logger.log('CRM URL: ' + CRM_BASE_URL);
  const resp = UrlFetchApp.fetch(CRM_BASE_URL + '/api/orders', {
    headers: { 'bypass-tunnel-reminder': '1' },
    muteHttpExceptions: true
  });
  Logger.log('Orders: ' + resp.getContentText());
}
