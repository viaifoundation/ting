#!/usr/bin/env node
/**
 * Upload Ting Bible Audio files (.mp3) to ting.weiai.ai (WordPress REST API)
 * Automatically categorizes, tags, and creates audio posts.
 * Filters OUT video files (.mp4).
 */

const fs = require('fs');
const path = require('path');
const { chromium } = require('playwright');

const WP_URL = "https://ting.weiai.ai/wp-json/wp/v2";
const AUTH_HEADER = "Basic " + Buffer.from("michaelhuo:oWCV Kh7h 77oL HILK Nsh8 CR07").toString("base64");

const REPO_ROOT = path.resolve(__dirname, '..');
const AUDIO_DIR = path.join(REPO_ROOT, 'audio');

// Category Mapping (slug -> ID)
const CATEGORY_MAP = {
    'chronological-1year': 2,
    'chronological-6month': 3,
    'wisdom-praise-6month': 4,
    'psalms-proverbs-372': 5,
    'wisdom-praise-30days': 6,
    'qt-daily': 7
};

// Tag Mapping (slug -> ID)
const TAG_MAP = {
    'rotate-voices': 8,
    'male-female-voices': 9,
    'cuv': 10,
    'everest-audio': 11,
    'bgm': 12,
    'psalms': 13,
    'proverbs': 14
};

function determineCategoryAndTags(relPath, fileName) {
    let catId = CATEGORY_MAP['qt-daily'];
    let tags = [TAG_MAP['cuv'], TAG_MAP['everest-audio']];

    if (relPath.includes('chronological-1year')) {
        catId = CATEGORY_MAP['chronological-1year'];
        tags.push(TAG_MAP['rotate-voices']);
    } else if (relPath.includes('psalms-proverbs-youversion-372-male-female')) {
        catId = CATEGORY_MAP['psalms-proverbs-372'];
        tags.push(TAG_MAP['male-female-voices'], TAG_MAP['psalms'], TAG_MAP['proverbs']);
    } else if (relPath.includes('psalms-proverbs-youversion-372-rotate')) {
        catId = CATEGORY_MAP['psalms-proverbs-372'];
        tags.push(TAG_MAP['rotate-voices'], TAG_MAP['psalms'], TAG_MAP['proverbs']);
    } else if (relPath.includes('wisdom-praise-30days')) {
        catId = CATEGORY_MAP['wisdom-praise-30days'];
        tags.push(TAG_MAP['psalms'], TAG_MAP['proverbs']);
    } else if (fileName.includes('半年歷史時序')) {
        catId = CATEGORY_MAP['chronological-6month'];
    } else if (fileName.includes('半年智慧讚美')) {
        catId = CATEGORY_MAP['wisdom-praise-6month'];
        tags.push(TAG_MAP['psalms'], TAG_MAP['proverbs']);
    }

    return { catId, tags: Array.from(new Set(tags)) };
}

function cleanTitle(fileName) {
    let name = path.basename(fileName, path.extname(fileName));
    name = name.replace(/^psalms-proverbs-youversion-372-/, '');
    name = name.replace(/^wisdom-praise-30days-/, '');
    return name;
}

async function main() {
    console.log("=== Starting Ting Audio WordPress Uploader ===");
    console.log("Scanning directory:", AUDIO_DIR);

    // Collect all MP3 files (IGNORE .mp4 videos)
    const audioFiles = [];
    function scanDir(dir) {
        if (!fs.existsSync(dir)) return;
        const entries = fs.readdirSync(dir, { withFileTypes: true });
        for (const entry of entries) {
            const fullPath = path.join(dir, entry.name);
            if (entry.isDirectory()) {
                scanDir(fullPath);
            } else if (entry.isFile()) {
                const ext = path.extname(entry.name).toLowerCase();
                if (ext === '.mp3') { // Strictly ONLY MP3 audio
                    audioFiles.push(fullPath);
                }
            }
        }
    }
    scanDir(AUDIO_DIR);

    // CLI Filter Arguments: --plan <name>, --day <num>, --date <YYYY-MM-DD>, --latest, --last-days <N>, --limit <N>
    const planArgIdx = process.argv.indexOf('--plan');
    const dayArgIdx = process.argv.indexOf('--day');
    const dateArgIdx = process.argv.indexOf('--date');
    const daysArgIdx = process.argv.indexOf('--last-days');
    const limitArgIdx = process.argv.indexOf('--limit');
    const isLatest = process.argv.includes('--latest');

    let filteredFiles = audioFiles;

    // Filter by Plan/Folder name
    if (planArgIdx !== -1 && process.argv[planArgIdx + 1]) {
        const planKeyword = process.argv[planArgIdx + 1].toLowerCase();
        filteredFiles = filteredFiles.filter(f => f.toLowerCase().includes(planKeyword));
    }

    // Filter by Day number (e.g. 74 or day074)
    if (dayArgIdx !== -1 && process.argv[dayArgIdx + 1]) {
        const dayNum = process.argv[dayArgIdx + 1];
        const dayPatterns = [`第${dayNum}天`, `day${dayNum.padStart(3, '0')}`, `day${dayNum}`];
        filteredFiles = filteredFiles.filter(f => dayPatterns.some(p => path.basename(f).includes(p)));
    }

    // Filter by specific Date (YYYY-MM-DD)
    if (dateArgIdx !== -1 && process.argv[dateArgIdx + 1]) {
        const targetDateStr = process.argv[dateArgIdx + 1];
        filteredFiles = filteredFiles.filter(f => {
            const mtime = fs.statSync(f).mtime;
            const fileDateStr = mtime.toISOString().split('T')[0];
            return fileDateStr === targetDateStr;
        });
    }

    // Filter by Last Days
    if (daysArgIdx !== -1 && process.argv[daysArgIdx + 1]) {
        const days = parseInt(process.argv[daysArgIdx + 1], 10);
        const cutoff = Date.now() - (days * 24 * 60 * 60 * 1000);
        filteredFiles = filteredFiles.filter(f => fs.statSync(f).mtimeMs >= cutoff);
    }

    // Filter to Latest per folder if --latest is passed
    if (isLatest && filteredFiles.length > 0) {
        const latestByFolder = {};
        for (const f of filteredFiles) {
            const dir = path.dirname(f);
            const mtime = fs.statSync(f).mtimeMs;
            if (!latestByFolder[dir] || mtime > latestByFolder[dir].mtime) {
                latestByFolder[dir] = { file: f, mtime };
            }
        }
        filteredFiles = Object.values(latestByFolder).map(item => item.file);
    }

    let fileLimit = filteredFiles.length;
    if (limitArgIdx !== -1 && process.argv[limitArgIdx + 1]) {
        fileLimit = parseInt(process.argv[limitArgIdx + 1], 10);
    }
    const targetFiles = filteredFiles.slice(0, fileLimit);

    console.log(`Found ${audioFiles.length} total MP3 files. Filtered to ${targetFiles.length} file(s) to process.`);
    if (targetFiles.length === 0) {
        console.log("No matching MP3 files found for specified criteria.");
        return;
    }

    // Launch Chromium for WAF session handling
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

    let successCount = 0;
    let skipCount = 0;

    for (const filePath of targetFiles) {
        const relPath = path.relative(AUDIO_DIR, filePath);
        const fileName = path.basename(filePath);
        const title = cleanTitle(fileName);
        const { catId, tags } = determineCategoryAndTags(relPath, fileName);

        const mtime = fs.statSync(filePath).mtime;
        const year = mtime.getFullYear();
        const month = String(mtime.getMonth() + 1).padStart(2, '0');
        const day = String(mtime.getDate()).padStart(2, '0');
        const hours = String(mtime.getHours()).padStart(2, '0');
        const minutes = String(mtime.getMinutes()).padStart(2, '0');
        const seconds = String(mtime.getSeconds()).padStart(2, '0');
        const fileDate = `${year}-${month}-${day}T${hours}:${minutes}:${seconds}`;

        console.log(`\nProcessing: ${relPath}`);
        console.log(`  Title: ${title} | Audio Date: ${fileDate}`);

        // Check if post already exists
        const existsRes = await page.evaluate(async (postTitle) => {
            const res = await fetch(`https://ting.weiai.ai/wp-json/wp/v2/posts?search=${encodeURIComponent(postTitle)}`);
            if (res.ok) {
                const posts = await res.json();
                const exact = posts.find(p => p.title.rendered === postTitle || p.title.raw === postTitle);
                return !!exact;
            }
            return false;
        }, title);

        if (existsRes) {
            console.log(`  ℹ Post already exists on WordPress, skipping: ${title}`);
            skipCount++;
            continue;
        }

        // Read file binary as base64 for page.evaluate transfer
        const fileBuf = fs.readFileSync(filePath);
        const base64Data = fileBuf.toString('base64');

        // 1. Upload Media via REST API
        const mediaRes = await page.evaluate(async ({ fileName, base64Data }) => {
            const byteCharacters = atob(base64Data);
            const byteNumbers = new Array(byteCharacters.length);
            for (let i = 0; i < byteCharacters.length; i++) {
                byteNumbers[i] = byteCharacters.charCodeAt(i);
            }
            const byteArray = new Uint8Array(byteNumbers);
            const blob = new Blob([byteArray], { type: 'audio/mpeg' });

            const res = await fetch("https://ting.weiai.ai/wp-json/wp/v2/media", {
                method: "POST",
                headers: {
                    "Content-Disposition": `attachment; filename="${encodeURIComponent(fileName)}"`,
                    "Content-Type": "audio/mpeg"
                },
                body: blob
            });
            let data;
            try {
                data = await res.json();
            } catch(e) {
                const text = await res.text().catch(() => "");
                data = { message: text || e.toString() };
            }
            return { status: res.status, data: data };
        }, { fileName, base64Data });

        if (mediaRes.status !== 201 && mediaRes.status !== 200) {
            console.log(`  ⚠️ Media Upload skipped/failed (${mediaRes.status}):`, (mediaRes.data?.message || mediaRes.data).slice(0, 100));
            const fallbackAudioUrl = `https://media.weiai.ai/audio/${encodeURIComponent(fileName)}`;
            console.log(`  ℹ Creating post with CDN fallback URL: ${fallbackAudioUrl}`);

            const postContent = `
<!-- wp:audio -->
<figure class="wp-block-audio"><audio controls src="${fallbackAudioUrl}"></audio></figure>
<!-- /wp:audio -->
<p><strong>朗读计划：</strong> ${title}</p>
            `.trim();

            const postData = {
                title: title,
                content: postContent,
                status: "publish",
                date: fileDate,
                categories: [catId],
                tags: tags
            };

            const postRes = await page.evaluate(async (pData) => {
                try {
                    const res = await fetch("https://ting.weiai.ai/wp-json/wp/v2/posts", {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify(pData)
                    });
                    return { status: res.status, data: await res.json() };
                } catch(err) {
                    return { status: 500, data: { message: err.toString() } };
                }
            }, postData);

            if (postRes.status === 201 || postRes.status === 200) {
                console.log(`  ✓ Post Published (CDN Fallback): ${postRes.data.link}`);
                successCount++;
            } else {
                console.log(`  ✗ Failed to publish post:`, postRes.status, postRes.data?.message || postRes.data);
            }
            continue;
        }

        const mediaId = mediaRes.data.id;
        const audioUrl = mediaRes.data.source_url;
        console.log(`  ✓ Media Uploaded: ID ${mediaId}, URL: ${audioUrl}`);

        // 2. Create Post
        const postContent = `
<!-- wp:audio {"id":${mediaId}} -->
<figure class="wp-block-audio"><audio controls src="${audioUrl}"></audio></figure>
<!-- /wp:audio -->
<p><strong>朗读计划：</strong> ${title}</p>
        `.trim();

        const postData = {
            title: title,
            content: postContent,
            status: "publish",
            date: fileDate,
            categories: [catId],
            tags: tags,
            featured_media: mediaId
        };

        const postRes = await page.evaluate(async (pData) => {
            const res = await fetch("https://ting.weiai.ai/wp-json/wp/v2/posts", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(pData)
            });
            return { status: res.status, data: await res.json() };
        }, postData);

        if (postRes.status === 201 || postRes.status === 200) {
            console.log(`  ✓ Post Published: ${postRes.data.link}`);
            successCount++;
        } else {
            console.log(`  ✗ Failed to publish post:`, postRes.status, postRes.data?.message || postRes.data);
        }
    }

    console.log(`\n=== Upload Completed: ${successCount} published, ${skipCount} skipped ===`);
    await browser.close();
}

main().catch(console.error);
