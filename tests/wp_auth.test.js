'use strict';
const { test } = require('node:test');
const assert = require('node:assert/strict');
const { getWordPressAuthHeader } = require('../scripts/wp_auth');

test('WordPress auth requires both environment variables and rejects malformed credentials', () => {
    const original = { ...process.env };
    try {
        for (const [username, password] of [['', ''], ['user', ''], ['', 'password'], ['user:admin', 'password'], ['user', 'password\r\nHeader: injected']]) {
            process.env.WP_USERNAME = username;
            process.env.WP_APP_PASSWORD = password;
            assert.throws(getWordPressAuthHeader, /Set WP_USERNAME and WP_APP_PASSWORD/);
        }
        process.env.WP_USERNAME = 'test-user';
        process.env.WP_APP_PASSWORD = 'test application password';
        assert.equal(Buffer.from(getWordPressAuthHeader().slice(6), 'base64').toString(), 'test-user:test application password');
    } finally {
        for (const key of ['WP_USERNAME', 'WP_APP_PASSWORD']) {
            if (original[key] === undefined) delete process.env[key];
            else process.env[key] = original[key];
        }
    }
});
