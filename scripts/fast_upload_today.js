#!/usr/bin/env node
const fs = require('fs');
const path = require('path');
const os = require('os');
const { execSync } = require('child_process');
const { chromium } = require('playwright');

const WP_URL = "https://ting.weiai.ai/wp-json/wp/v2";
const AUTH_HEADER = "Basic " + Buffer.from("michaelhuo:oWCV Kh7h 77oL HILK Nsh8 CR07").toString("base64");
const REPO_ROOT = path.resolve(__dirname, '..');
const AUDIO_DIR = path.join(REPO_ROOT, 'audio');

const CATEGORY_MAP = {
    'chronological-1year': 2,
    'chronological-6month': 3,
    'wisdom-praise-6month': 4,
    'psalms-proverbs-372': 5,
    'wisdom-praise-30days': 6,
    'qt-daily': 7
};

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

    if (fileName.includes('年度歷史時序') || relPath.includes('chronological-1year')) {
        catId = CATEGORY_MAP['chronological-1year'];
    } else if (fileName.includes('372天智慧讚美') || relPath.includes('psalms-proverbs-youversion-372')) {
        catId = CATEGORY_MAP['psalms-proverbs-372'];
        tags.push(TAG_MAP['psalms'], TAG_MAP['proverbs']);
    } else if (fileName.includes('31天智慧讚美') || relPath.includes('wisdom-praise-30days') || relPath.includes('youversion-31')) {
        catId = CATEGORY_MAP['wisdom-praise-30days'];
        tags.push(TAG_MAP['psalms'], TAG_MAP['proverbs']);
    } else if (fileName.includes('半年歷史時序') || relPath.includes('chronological-6month')) {
        catId = CATEGORY_MAP['chronological-6month'];
    } else if (fileName.includes('半年智慧讚美') || relPath.includes('wisdom-praise-6month')) {
        catId = CATEGORY_MAP['wisdom-praise-6month'];
        tags.push(TAG_MAP['psalms'], TAG_MAP['proverbs']);
    }

    if (fileName.includes('對照') || relPath.includes('male-female')) {
        tags.push(TAG_MAP['male-female-voices']);
    } else {
        tags.push(TAG_MAP['rotate-voices']);
    }

    return { catId, tags: Array.from(new Set(tags)) };
}

function cleanTitle(fileName) {
    let name = path.basename(fileName, path.extname(fileName));
    name = name.replace(/^psalms-proverbs-youversion-372-/, '');
    name = name.replace(/^wisdom-praise-30days-/, '');
    return name;
}

function buildPostContent(filePath, title, audioUrl, mediaId = null) {
    const txtPath = filePath.replace(/\.mp3$/i, '.txt');
    let bibleHtml = '';

    if (fs.existsSync(txtPath)) {
        const txtRaw = fs.readFileSync(txtPath, 'utf8').trim();
        const lines = txtRaw.split('\n');
        bibleHtml = lines.map(line => {
            const trimmed = line.trim();
            if (!trimmed) return '';
            if (trimmed.startsWith('內容取自') || trimmed.startsWith('聖經語音') || trimmed.startsWith('閱讀聆聽')) {
                return `<p><em>${trimmed}</em></p>`;
            }
            if (trimmed.match(/^(?:[\u4e00-\u9fa5\w\s]+)\s+第\d+章$/)) {
                return `<h3>${trimmed}</h3>`;
            }
            return `<p>${trimmed}</p>`;
        }).filter(Boolean).join('\n');
    } else {
        bibleHtml = `
<p><strong>朗讀計劃：</strong> ${title}</p>
<p><em>內容取自 YouVersion「今日經文」與「讀經計劃」。</em></p>
<p><em>聖經語音由 Everest (女聲) 與 閻大衛 (男聲) 老師提供。</em></p>
<p><em>閱讀聆聽，盡在唯愛 AI 基金會。VOTD 今日經文：https://votd.vi.fyi，Shema 讀經計劃：https://ting.vi.fyi</em></p>
        `.trim();
    }

    const audioBlock = mediaId
        ? `<!-- wp:audio {"id":${mediaId}} -->\n<figure class="wp-block-audio"><audio controls src="${audioUrl}"></audio></figure>\n<!-- /wp:audio -->`
        : `<!-- wp:audio -->\n<figure class="wp-block-audio"><audio controls src="${audioUrl}"></audio></figure>\n<!-- /wp:audio -->`;

    return `${audioBlock}\n\n<div class="bible-post-content">\n${bibleHtml}\n</div>`;
}

async function main() {
    console.log("=== Fast Upload Today's Ting Audio Files to WordPress ===");

    const dateArgIdx = process.argv.indexOf('--date');
    const dirArgIdx = process.argv.indexOf('--dir');
    let targetDir = null;

    if (dirArgIdx !== -1 && process.argv[dirArgIdx + 1]) {
        targetDir = path.resolve(process.argv[dirArgIdx + 1]);
    } else if (dateArgIdx !== -1 && process.argv[dateArgIdx + 1]) {
        targetDir = path.join(AUDIO_DIR, process.argv[dateArgIdx + 1].trim());
    } else {
        const todayPdt = new Intl.DateTimeFormat('en-CA', {
            timeZone: 'America/Los_Angeles',
            year: 'numeric',
            month: '2-digit',
            day: '2-digit'
        }).format(new Date()).replace(/-/g, '');
        const todayDir = path.join(AUDIO_DIR, todayPdt);
        if (fs.existsSync(todayDir)) {
            targetDir = todayDir;
        }
    }

    const audioFiles = [];
    if (targetDir && fs.existsSync(targetDir)) {
        console.log(`Scanning target directory: ${targetDir}`);
        const entries = fs.readdirSync(targetDir, { withFileTypes: true });
        for (const entry of entries) {
            const fullPath = path.join(targetDir, entry.name);
            if (entry.isFile() && path.extname(entry.name).toLowerCase() === '.mp3') {
                audioFiles.push(fullPath);
            }
        }
    } else {
        const now = Date.now();
        const scanWindowMs = 18 * 60 * 60 * 1000;
        function scanDir(dir) {
            if (!fs.existsSync(dir)) return;
            const entries = fs.readdirSync(dir, { withFileTypes: true });
            for (const entry of entries) {
                const fullPath = path.join(dir, entry.name);
                if (entry.isDirectory()) {
                    scanDir(fullPath);
                } else if (entry.isFile() && path.extname(entry.name).toLowerCase() === '.mp3') {
                    const stat = fs.statSync(fullPath);
                    if (now - stat.mtimeMs <= scanWindowMs) {
                        audioFiles.push(fullPath);
                    }
                }
            }
        }
        scanDir(AUDIO_DIR);
    }
    audioFiles.sort((a, b) => fs.statSync(b).mtimeMs - fs.statSync(a).mtimeMs);

    console.log(`Found ${audioFiles.length} MP3 files to process.`);

    const browser = await chromium.launch({ headless: true });
    const context = await browser.newContext();
    const page = await context.newPage();

    console.log("Solving WAF challenge at https://ting.weiai.ai...");
    await page.goto("https://ting.weiai.ai/", { waitUntil: "networkidle" });
    await page.waitForTimeout(2000);

    let successCount = 0;

    for (const filePath of audioFiles) {
        const fileName = path.basename(filePath);
        const relPath = path.relative(AUDIO_DIR, filePath);
        const title = cleanTitle(fileName);
        const { catId, tags } = determineCategoryAndTags(relPath, fileName);
        const stat = fs.statSync(filePath);
        const fileDate = new Date(stat.mtimeMs).toISOString();

        console.log(`\nProcessing: ${relPath}`);
        console.log(`  Title: ${title} | Category: ${catId}`);

        // Check if post already published
        const existingCheck = await page.evaluate(async ({ searchTitle, authHeader }) => {
            try {
                const res = await fetch(`https://ting.weiai.ai/wp-json/wp/v2/posts?search=${encodeURIComponent(searchTitle)}&per_page=5`, {
                    headers: { "Authorization": authHeader }
                });
                if (res.ok) {
                    const posts = await res.json();
                    const match = posts.find(p => p.title.rendered.includes(searchTitle));
                    if (match) {
                        const todayStr = new Date().toISOString().slice(0, 10);
                        const isToday = match.date.startsWith(todayStr);
                        const hasBrokenMedia = (match.content && match.content.rendered) 
                            ? match.content.rendered.includes('media.weiai.ai') 
                            : false;
                        return { exists: true, id: match.id, link: match.link, isToday, hasBrokenMedia };
                    }
                }
                return { exists: false };
            } catch(e) {
                return { exists: false };
            }
        }, { searchTitle: title, authHeader: AUTH_HEADER });

        if (existingCheck.exists && existingCheck.isToday && !existingCheck.hasBrokenMedia) {
            console.log(`  ⏭️ Post already exists and is healthy: ${existingCheck.link}`);
            successCount++;
            continue;
        }

        if (existingCheck.exists) {
            if (existingCheck.hasBrokenMedia) {
                console.log(`  🔄 Post exists (${existingCheck.id}) but has broken audio URL. Re-uploading media and updating...`);
            } else if (!existingCheck.isToday) {
                console.log(`  🔄 Post exists from older date (${existingCheck.id}). Updating date to today and refreshing media...`);
            }
        }

        // Upload media inside page evaluation context (bypasses WAF with cookies)
        let uploadBuffer = fs.readFileSync(filePath);
        let uploadName = fileName;
        let tempCompressedFile = null;

        // If file > 10MB, optimize with ffmpeg to ensure smooth upload and prevent server body size rejection
        if (uploadBuffer.length > 10 * 1024 * 1024) {
            tempCompressedFile = path.join(os.tmpdir(), `compressed_${Date.now()}_audio.mp3`);
            const targetBitrate = uploadBuffer.length > 25 * 1024 * 1024 ? '96k' : '128k';
            console.log(`  ⚡ Optimizing audio bitrate to ${targetBitrate} (${(uploadBuffer.length / 1024 / 1024).toFixed(1)} MB)...`);
            try {
                execSync(`ffmpeg -y -i "${filePath}" -codec:a libmp3lame -b:a ${targetBitrate} "${tempCompressedFile}"`, { stdio: 'ignore' });
                if (fs.existsSync(tempCompressedFile) && fs.statSync(tempCompressedFile).size > 0) {
                    uploadBuffer = fs.readFileSync(tempCompressedFile);
                    console.log(`  ✓ Compressed to ${(uploadBuffer.length / 1024 / 1024).toFixed(1)} MB`);
                }
            } catch (err) {
                console.warn(`  ⚠️ Optimization failed, proceeding with original file:`, err.message);
            }
        }

        let mediaRes = null;

        for (let attempt = 1; attempt <= 3; attempt++) {
            console.log(`  Uploading audio binary (${(uploadBuffer.length / 1024 / 1024).toFixed(1)} MB) [Attempt ${attempt}]...`);
            try {
                const response = await context.request.post("https://ting.weiai.ai/wp-json/wp/v2/media", {
                    headers: {
                        "Authorization": AUTH_HEADER,
                        "Content-Type": "audio/mpeg",
                        "Content-Disposition": `attachment; filename="${encodeURIComponent(uploadName)}"`
                    },
                    data: uploadBuffer,
                    timeout: 180000
                });

                const status = response.status();
                let data;
                try { data = await response.json(); } catch(e) { data = { message: response.statusText() }; }
                mediaRes = { status, data };

                if (status === 201 || status === 200) {
                    break;
                }
                console.log(`  ⚠️ Attempt ${attempt} failed (${status}): ${data?.message || 'unknown'}. Refreshing WAF & Retrying in 3s...`);
            } catch (err) {
                console.log(`  ⚠️ Attempt ${attempt} error: ${err.message}. Retrying in 3s...`);
                mediaRes = { status: 500, data: { message: err.message } };
            }
            try {
                await page.goto("https://ting.weiai.ai/", { waitUntil: "networkidle" });
            } catch(e) {}
            await page.waitForTimeout(3000);
        }

        if (tempCompressedFile && fs.existsSync(tempCompressedFile)) {
            try { fs.unlinkSync(tempCompressedFile); } catch(e) {}
        }

        let mediaId = null;
        let audioUrl = null;

        if (mediaRes && (mediaRes.status === 201 || mediaRes.status === 200)) {
            mediaId = mediaRes.data.id;
            audioUrl = mediaRes.data.source_url;
            console.log(`  ✓ Media Uploaded: ID ${mediaId}`);
        } else {
            audioUrl = `https://media.weiai.ai/audio/${encodeURIComponent(fileName)}`;
            console.log(`  ℹ️ WP Media upload bypassed/failed (${mediaRes?.status}). Using CDN Fallback URL: ${audioUrl}`);
        }

        // Create or update post
        const postContent = buildPostContent(filePath, title, audioUrl, mediaId);
        const postData = {
            title: title,
            content: postContent,
            status: "publish",
            date: fileDate,
            categories: [catId],
            tags: tags
        };
        if (mediaId) {
            postData.featured_media = mediaId;
        }

        let postRes = null;
        if (existingCheck.exists) {
            // Update existing post
            postRes = await page.evaluate(async ({ postId, pData, authHeader }) => {
                try {
                    const res = await fetch(`https://ting.weiai.ai/wp-json/wp/v2/posts/${postId}`, {
                        method: "POST",
                        headers: {
                            "Authorization": authHeader,
                            "Content-Type": "application/json"
                        },
                        body: JSON.stringify(pData)
                    });
                    return { status: res.status, data: await res.json() };
                } catch(err) {
                    return { status: 500, data: { message: err.toString() } };
                }
            }, { postId: existingCheck.id, pData: postData, authHeader: AUTH_HEADER });
        } else {
            // Create new post
            postRes = await page.evaluate(async ({ pData, authHeader }) => {
                try {
                    const res = await fetch("https://ting.weiai.ai/wp-json/wp/v2/posts", {
                        method: "POST",
                        headers: {
                            "Authorization": authHeader,
                            "Content-Type": "application/json"
                        },
                        body: JSON.stringify(pData)
                    });
                    return { status: res.status, data: await res.json() };
                } catch(err) {
                    return { status: 500, data: { message: err.toString() } };
                }
            }, { pData: postData, authHeader: AUTH_HEADER });
        }

        if (postRes.status === 201 || postRes.status === 200) {
            console.log(`  🎉 Post Published/Updated: ${postRes.data.link}`);
            successCount++;
        } else {
            console.log(`  ✗ Failed to save post (${postRes.status}):`, postRes.data?.message || postRes.data);
        }
        await page.waitForTimeout(2000);
    }

    console.log(`\n=== Fast Upload Finished: ${successCount}/${audioFiles.length} Published ===`);
    await browser.close();
}

main().catch(console.error);
