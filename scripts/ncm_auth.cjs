let ncm;
try {
  ncm = require('NeteaseCloudMusicApi');
} catch (e) {
  const path = require('path');
  ncm = require(path.join(__dirname, '..', 'vendor', 'ncm_modules', 'NeteaseCloudMusicApi'));
}

async function main() {
  const action = process.argv[2];
  if (action === 'get_qr') {
    const k = await ncm.login_qr_key({});
    const unikey = k.body?.data?.unikey;
    if (!unikey) throw new Error('未能获取网易云登录密钥');
    const qr = await ncm.login_qr_create({ key: unikey, platform: 'web', qrimg: true });
    console.log(JSON.stringify({
      ok: true,
      unikey,
      qr_url: qr.body?.data?.qrurl,
      qr_img: qr.body?.data?.qrimg
    }));
  } else if (action === 'check_qr') {
    const unikey = process.argv[3];
    if (!unikey) throw new Error('缺少 unikey');
    const chk = await ncm.login_qr_check({ key: unikey });
    console.log(JSON.stringify({
      ok: true,
      ...chk.body
    }));
  } else {
    throw new Error('未知的操作: ' + action);
  }
}

main().catch(err => {
  console.log(JSON.stringify({ ok: false, error: err.message || String(err) }));
  process.exit(1);
});
