'use strict';

function getWordPressAuthHeader() {
    const username = process.env.WP_USERNAME;
    const password = process.env.WP_APP_PASSWORD;
    if (!username || !password || username.includes(':') || /[\r\n]/.test(username + password)) {
        throw new Error('Set WP_USERNAME and WP_APP_PASSWORD to your WordPress application credentials');
    }
    return 'Basic ' + Buffer.from(`${username}:${password}`).toString('base64');
}

module.exports = { getWordPressAuthHeader };
