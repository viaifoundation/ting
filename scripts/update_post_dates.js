#!/usr/bin/env node
/**
 * Update existing WordPress post dates to match the modification date (mtime) of the audio file.
 */

const fs = require('fs');
const path = require('path');
const { chromium } = require('playwright');

const WP_URL = "https://ting.weiai.ai/wp-json/wp/v2";
const AUTH_HEADER = "Basic " + Buffer.from("michaelhuo:oWCV Kh7h 77oL HILK Nsh8 CR07").toString("base64");

const REPO_ROOT = path.resolve(__dirname, '..');
const AUDIO_DIR = path.join(REPO_ROOT, 'audio');

// Build title -> mtime map
const audioMap = {};
function scanDir(dir) {
    if (!fs.existsSync(dir)) return;
    const entries = fs.readdirSync(dir, { withFileTypes: true });
    for (const entry of entries) {
        const fullPath = path.join(dir, entry.name);
        if (entry.isDirectory()) {
            scanDir(fullPath);
        } else if (entry.isFile() && path.extname(entry.name).toLowerCase() === '.mp3') {
            let name = path.basename(entry.name, '.mp3');
            name = name.replace(/^psalms-proverbs-youversion-372-/, '');
            name = name.replace(/^wisdom-praise-30days-/, '');
            const mtime = fs.statSync(fullPath).mtime;
            // Format to ISO local format: YYYY-MM-DDTHH:mm:ss
            const year = mtime.getFullYear();
            const month = String(mtime.getMonth() + 1).padStart(2, '0');
            const day = String(mtime.getDate()).padStart(2, '0');
            const hours = String(mtime.getHours()).padStart(2, '0');
            const minutes = String(mtime.getMinutes()).padStart(2, '0');
            const seconds = String(mtime.getSeconds()).padStart(2, '0');
            const isoStr = `${year}-${month}-${day}T${hours}:${minutes}:${seconds}`;

            audioMap[name] = isoStr;
        }
    }
}
scanDir(AUDIO_DIR);

console.log(`Mapped ${Object.keys(audioMap).length} audio titles to file modification dates.`);

async function main() {
    console.log("Launching Chromium via Playwright...");
    const browser = await chromium.launch({
        headless: true,
        args: ['--disable-blink-features=AutomationControlled']
    });
    const context = await browser.newContext();
    const page = await context.newPage();

    console.log("Navigating to https://ting.weiai.ai/ to solve WAF challenge...");
    await page.goto("https://ting.weiai.ai/", { waitUntil: "networkidle" });
    await page.waitForTimeout(3000);

    await page.setExtraHTTPHeaders({ 'Authorization': AUTH_HEADER });

    // Fetch all posts
    console.log("Fetching existing posts from WordPress...");
    const posts = await page.evaluate(async () => {
        const res = await fetch("https://ting.weiai.ai/wp-json/wp/v2/posts?per_page=100");
        return await res.json();
    });

    console.log(`Found ${posts.length} posts on WordPress.\n`);

    let updatedCount = 0;
    for (const post of posts) {
        const title = post.title.raw || post.title.rendered;
        const postId = post.id;
        const currentDate = post.date;

        if (audioMap[title]) {
            const targetDate = audioMap[title];
            console.log(`Post [ID ${postId}] "${title}":`);
            console.log(`  Current Date: ${currentDate}`);
            console.log(`  Target Date:  ${targetDate}`);

            if (currentDate !== targetDate) {
                const updateRes = await page.evaluate(async ({ id, targetDate }) => {
                    const res = await fetch(`https://ting.weiai.ai/wp-json/wp/v2/posts/${id}`, {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({ date: targetDate })
                    });
                    return { status: res.status, data: await res.json() };
                }, { id: postId, targetDate });

                if (updateRes.status === 200) {
                    console.log(`  ✓ Updated date to: ${updateRes.data.date}`);
                    updatedCount++;
                } else {
                    console.log(`  ✗ Error updating date:`, updateRes.status, updateRes.data);
                }
            } else {
                console.log(`  ℹ Date already matches.`);
            }
        } else {
            console.log(`Post [ID ${postId}] "${title}" -> No local audio file match.`);
        }
        console.log("");
    }

    console.log(`=== Done: Updated ${updatedCount} post dates. ===`);
    await browser.close();
}

main().catch(console.error);
