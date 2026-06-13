/**
 * DOZENKO — Google Apps Script
 * Dán toàn bộ code này vào Google Apps Script
 * Sau đó Deploy > Web App và copy URL vào script.js
 */

function doPost(e) {
  try {
    const sheet = SpreadsheetApp.getActiveSpreadsheet().getActiveSheet();
    
    // Tạo header nếu sheet trống
    if (sheet.getLastRow() === 0) {
      sheet.appendRow([
        'Timestamp', 'Name', 'Email', 'Phone',
        'Quantity', 'Price', 'Colors', 'Address', 'Notes', 'Status'
      ]);
      // Format header
      sheet.getRange(1, 1, 1, 10).setBackground('#2A4E7C').setFontColor('#FFFFFF').setFontWeight('bold');
    }

    // Parse data
    const data = JSON.parse(e.postData.contents);
    
    // Append row
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
      'New' // Status mặc định
    ]);

    // Auto-resize columns
    sheet.autoResizeColumns(1, 10);

    return ContentService
      .createTextOutput(JSON.stringify({ success: true }))
      .setMimeType(ContentService.MimeType.JSON);

  } catch (err) {
    return ContentService
      .createTextOutput(JSON.stringify({ success: false, error: err.toString() }))
      .setMimeType(ContentService.MimeType.JSON);
  }
}

// Test function - chạy thử trong Apps Script
function testSetup() {
  const sheet = SpreadsheetApp.getActiveSpreadsheet().getActiveSheet();
  Logger.log('Sheet name: ' + sheet.getName());
  Logger.log('Setup OK!');
}
