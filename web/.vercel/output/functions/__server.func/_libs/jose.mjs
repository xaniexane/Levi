import { JOSEAlgNotAllowed, JOSENotSupported, JWE, JWEDecryptionFailed, JWEInvalid, JWE_RECOGNIZED, JWKInvalid, JWSInvalid, JWS_RECOGNIZED, JWTClaimValidationFailed, JWTClaimsBuilder, JWTInvalid, assertCryptoKey, assertNotSet, assertUint8Array, checkCryptoKey, checkModulusLength, checkUsage, concat, decodeBase64url, decoder, digest, encode as encode$1, encode$1 as encode, encodeBase64url, encoder, invalidKeyInput, isCryptoKey, isDisjoint, isJWECEKTransport, isKeyLike, isKeyObject, isObject, jweAlgorithm, jweEncryption, jwkToKey, jwsAlgorithm, jwtClaim, jwtData, parseJoseHeader, prepareKey, rawKey, serializeJoseHeader, snapshotJwk, uint32be, uint64be, validateAlgorithms, validateB64, validateClaimsSet, validateCrit, validateCritDuplicates } from "./@better-auth/core+[...].mjs";
//#region node_modules/jose/dist/webapi/lib/content_encryption.js
var generateCek = (enc) => crypto.getRandomValues(new Uint8Array(enc.cekBits >> 3));
function checkCekLength(cek, expected) {
	const actual = cek.byteLength << 3;
	if (actual !== expected) throw new JWEInvalid(`Invalid Content Encryption Key length. Expected ${expected} bits, got ${actual} bits`);
}
var generateIv = (enc) => crypto.getRandomValues(new Uint8Array(enc.ivBits >> 3));
function checkIvLength(enc, iv) {
	if (iv.length << 3 !== enc.ivBits) throw new JWEInvalid("Invalid Initialization Vector length");
}
async function cbcKeySetup(enc, cek, usage) {
	if (!(cek instanceof Uint8Array)) throw new TypeError(invalidKeyInput(cek, "Uint8Array"));
	const keySize = enc.cekBits >> 1;
	return [
		await crypto.subtle.importKey("raw", cek.subarray(keySize >> 3), "AES-CBC", !1, [usage]),
		await crypto.subtle.importKey("raw", cek.subarray(0, keySize >> 3), {
			hash: `SHA-${keySize << 1}`,
			name: "HMAC"
		}, !1, ["sign"]),
		keySize
	];
}
async function cbcHmacTag(macKey, macData, keySize) {
	return new Uint8Array((await crypto.subtle.sign("HMAC", macKey, macData)).slice(0, keySize >> 3));
}
async function cbcEncrypt(enc, plaintext, cek, iv, aad) {
	const [encKey, macKey, keySize] = await cbcKeySetup(enc, cek, "encrypt"), ciphertext = new Uint8Array(await crypto.subtle.encrypt({
		iv,
		name: "AES-CBC"
	}, encKey, plaintext));
	return {
		ciphertext,
		tag: await cbcHmacTag(macKey, concat(aad, iv, ciphertext, uint64be(aad.length * 8)), keySize),
		iv
	};
}
async function timingSafeEqual(a, b) {
	const algorithm = {
		name: "HMAC",
		hash: "SHA-256"
	}, key = await crypto.subtle.generateKey(algorithm, !1, ["sign", "verify"]), aHmac = await crypto.subtle.sign(algorithm, key, a);
	return crypto.subtle.verify(algorithm, key, aHmac, b);
}
async function cbcDecrypt(enc, cek, ciphertext, iv, tag, aad) {
	const [encKey, macKey, keySize] = await cbcKeySetup(enc, cek, "decrypt"), expectedTag = await cbcHmacTag(macKey, concat(aad, iv, ciphertext, uint64be(aad.length * 8)), keySize);
	try {
		if (await timingSafeEqual(tag, expectedTag)) return new Uint8Array(await crypto.subtle.decrypt({
			iv,
			name: "AES-CBC"
		}, encKey, ciphertext));
	} catch {}
	throw new JWEDecryptionFailed();
}
async function encrypt(enc, plaintext, cek, iv, aad) {
	if (!isCryptoKey(cek) && !(cek instanceof Uint8Array)) throw new TypeError(invalidKeyInput(cek, "CryptoKey", "KeyObject", "Uint8Array", "JSON Web Key"));
	if (iv ? checkIvLength(enc, iv) : iv = generateIv(enc), cek instanceof Uint8Array && checkCekLength(cek, enc.cekBits), enc.cbc) return cbcEncrypt(enc, plaintext, cek, iv, aad);
	const encKey = await rawKey(cek, enc.subtle, "encrypt"), encrypted = new Uint8Array(await crypto.subtle.encrypt({
		additionalData: aad,
		iv,
		name: "AES-GCM",
		tagLength: 128
	}, encKey, plaintext));
	return {
		ciphertext: encrypted.subarray(0, -16),
		tag: encrypted.subarray(-16),
		iv
	};
}
async function decrypt(enc, cek, ciphertext, iv, tag, aad) {
	if (!isCryptoKey(cek) && !(cek instanceof Uint8Array)) throw new TypeError(invalidKeyInput(cek, "CryptoKey", "KeyObject", "Uint8Array", "JSON Web Key"));
	if (!iv) throw new JWEInvalid("JWE Initialization Vector missing");
	if (!tag) throw new JWEInvalid("JWE Authentication Tag missing");
	if (!enc.cbc && tag.length !== 16) throw new JWEInvalid("Invalid Authentication Tag length");
	if (checkIvLength(enc, iv), cek instanceof Uint8Array && checkCekLength(cek, enc.cekBits), enc.cbc) return cbcDecrypt(enc, cek, ciphertext, iv, tag, aad);
	const encKey = await rawKey(cek, enc.subtle, "decrypt");
	try {
		return new Uint8Array(await crypto.subtle.decrypt({
			additionalData: aad,
			iv,
			name: "AES-GCM",
			tagLength: 128
		}, encKey, concat(ciphertext, tag)));
	} catch {
		throw new JWEDecryptionFailed();
	}
}
//#endregion
//#region node_modules/jose/dist/webapi/lib/key_management.js
function checkEcdhCryptoKey(key, usage) {
	if (key.algorithm.name !== "ECDH" && key.algorithm.name !== "X25519") throw new TypeError("CryptoKey does not support this operation, its algorithm.name must be ECDH or X25519");
	checkUsage(key, usage);
}
async function aeskwWrap(alg, key, cek) {
	const cryptoKey = await rawKey(key, jweAlgorithm(alg).subtle, "wrapKey", !0), cryptoKeyCek = await crypto.subtle.importKey("raw", cek, {
		hash: "SHA-256",
		name: "HMAC"
	}, !0, ["sign"]);
	return new Uint8Array(await crypto.subtle.wrapKey("raw", cryptoKeyCek, cryptoKey, "AES-KW"));
}
async function aeskwUnwrap(alg, key, encryptedKey) {
	const cryptoKey = await rawKey(key, jweAlgorithm(alg).subtle, "unwrapKey", !0), cryptoKeyCek = await crypto.subtle.unwrapKey("raw", encryptedKey, cryptoKey, "AES-KW", {
		hash: "SHA-256",
		name: "HMAC"
	}, !0, ["sign"]);
	return new Uint8Array(await crypto.subtle.exportKey("raw", cryptoKeyCek));
}
function checkRsaKey(alg, key, usage) {
	checkCryptoKey(key, jweAlgorithm(alg).subtle, usage), checkModulusLength(alg, key);
}
async function deriveKey(p2s, alg, p2c, key) {
	if (!(p2s instanceof Uint8Array) || p2s.length < 8) throw new JWEInvalid("PBES2 Salt Input must be 8 or more octets");
	if (!Number.isSafeInteger(p2c) || Math.sign(p2c) !== 1) throw new JWEInvalid("PBES2 Count Input must be a positive integer");
	const salt = concat(encode(alg), Uint8Array.of(0), p2s), keylen = parseInt(alg.slice(13, 16), 10), subtleAlg = {
		hash: `SHA-${alg.slice(8, 11)}`,
		iterations: p2c,
		name: "PBKDF2",
		salt
	}, cryptoKey = await rawKey(key, jweAlgorithm(alg).subtle, "deriveBits");
	return new Uint8Array(await crypto.subtle.deriveBits(subtleAlg, cryptoKey, keylen));
}
function lengthAndInput(input) {
	return concat(uint32be(input.length), input);
}
async function concatKdf(Z, L, OtherInfo) {
	const dkLen = L >> 3, hashLen = 32, reps = Math.ceil(dkLen / hashLen), dk = new Uint8Array(reps * hashLen);
	for (let i = 1; i <= reps; i++) {
		const hashResult = await digest("sha256", concat(uint32be(i), Z, OtherInfo));
		dk.set(hashResult, (i - 1) * hashLen);
	}
	return dk.slice(0, dkLen);
}
async function ecdhesDeriveKey(publicKey, privateKey, algorithm, keyLength, apu = /* @__PURE__ */ new Uint8Array(), apv = /* @__PURE__ */ new Uint8Array()) {
	checkEcdhCryptoKey(publicKey), checkEcdhCryptoKey(privateKey, "deriveBits");
	const otherInfo = concat(lengthAndInput(encode(algorithm)), lengthAndInput(apu), lengthAndInput(apv), uint32be(keyLength));
	return concatKdf(new Uint8Array(await crypto.subtle.deriveBits({
		name: publicKey.algorithm.name,
		public: publicKey
	}, privateKey, publicKey.algorithm.name === "X25519" ? 256 : Math.ceil(parseInt(publicKey.algorithm.namedCurve.slice(-3), 10) / 8) << 3)), keyLength, otherInfo);
}
function assertEcdhKey(key) {
	assertCryptoKey(key);
	const curve = key.algorithm.namedCurve;
	if (curve !== "P-256" && curve !== "P-384" && curve !== "P-521" && key.algorithm.name !== "X25519") throw new JOSENotSupported("ECDH with the provided key is not allowed or not supported by your javascript runtime");
}
function partyInfo(joseHeader, name) {
	const value = joseHeader[name];
	if (value !== void 0) {
		if (typeof value != "string") throw new JWEInvalid(`JOSE Header "${name}" (Agreement Party${name === "apu" ? "U" : "V"}Info) invalid`);
		return decodeBase64url(value, name, JWEInvalid);
	}
}
function checkPartyInfo(apu, apv) {
	if (!(apu === void 0 || apv === void 0 || apu.byteLength !== apv.byteLength)) {
		for (let i = 0; i < apu.byteLength; i++) if (apu[i] !== apv[i]) return;
		throw new JWEInvalid("JOSE Header \"apu\" and \"apv\" values must be distinct");
	}
}
function assertEncryptedKey(encryptedKey) {
	if (encryptedKey === void 0) throw new JWEInvalid("JWE Encrypted Key missing");
}
function assertNoEncryptedKey(encryptedKey) {
	if (encryptedKey !== void 0) throw new JWEInvalid("Encountered unexpected JWE Encrypted Key");
}
function validateMaxPBES2Count(value) {
	if (value !== void 0 && value !== 1 / 0 && (!Number.isSafeInteger(value) || value < 1)) throw new TypeError("maxPBES2Count must be a positive safe integer or Infinity");
}
async function decryptKeyManagement(entry, enc, key, encryptedKey, joseHeader, maxPBES2Count) {
	const { alg } = entry, mode = entry.mode;
	if (mode === "direct-encryption") return assertNoEncryptedKey(encryptedKey), key;
	const direct = mode === "direct-key-agreement";
	switch (direct ? assertNoEncryptedKey(encryptedKey) : assertEncryptedKey(encryptedKey), entry.subtle.name) {
		case "ECDH": {
			const { epk } = joseHeader;
			if (!isObject(epk) || [
				"d",
				"k",
				"p",
				"q",
				"dp",
				"dq",
				"qi",
				"oth",
				"priv"
			].some((parameter) => Object.hasOwn(epk, parameter))) throw new JWEInvalid("JOSE Header \"epk\" (Ephemeral Public Key) missing or invalid");
			assertEcdhKey(key);
			const ephemeralPublicKey = await jwkToKey(entry, epk), partyUInfo = partyInfo(joseHeader, "apu"), partyVInfo = partyInfo(joseHeader, "apv");
			checkPartyInfo(partyUInfo, partyVInfo);
			const sharedSecret = await ecdhesDeriveKey(ephemeralPublicKey, key, direct ? enc.alg : alg, direct ? enc.cekBits : parseInt(alg.slice(-5, -2), 10), partyUInfo, partyVInfo);
			if (direct) return sharedSecret;
			key = sharedSecret;
			break;
		}
		case "RSA-OAEP": return assertCryptoKey(key), checkRsaKey(alg, key, "decrypt"), new Uint8Array(await crypto.subtle.decrypt("RSA-OAEP", key, encryptedKey));
		case "PBKDF2": {
			if (typeof joseHeader.p2c != "number") throw new JWEInvalid("JOSE Header \"p2c\" (PBES2 Count) missing or invalid");
			validateMaxPBES2Count(maxPBES2Count);
			const p2cLimit = maxPBES2Count ?? 1e4;
			if (joseHeader.p2c > p2cLimit) throw new JWEInvalid("JOSE Header \"p2c\" (PBES2 Count) out is of acceptable bounds");
			if (typeof joseHeader.p2s != "string") throw new JWEInvalid("JOSE Header \"p2s\" (PBES2 Salt) missing or invalid");
			key = await deriveKey(decodeBase64url(joseHeader.p2s, "p2s", JWEInvalid), alg, joseHeader.p2c, key);
			break;
		}
		case "AES-GCM": {
			if (typeof joseHeader.iv != "string") throw new JWEInvalid("JOSE Header \"iv\" (Initialization Vector) missing or invalid");
			if (typeof joseHeader.tag != "string") throw new JWEInvalid("JOSE Header \"tag\" (Authentication Tag) missing or invalid");
			const iv = decodeBase64url(joseHeader.iv, "iv", JWEInvalid), tag = decodeBase64url(joseHeader.tag, "tag", JWEInvalid);
			if (iv.byteLength !== 12) throw new JWEInvalid("Invalid Initialization Vector length");
			if (tag.byteLength !== 16) throw new JWEInvalid("Invalid Authentication Tag length");
			return decrypt(jweEncryption(alg.slice(0, -2)), key, encryptedKey, iv, tag, /* @__PURE__ */ new Uint8Array());
		}
	}
	return aeskwUnwrap(alg.slice(-6), key, encryptedKey);
}
async function encryptKeyManagement(entry, enc, inputKey, joseHeader, providedCek, providedParameters = {}) {
	const { alg, mode } = entry, transport = isJWECEKTransport(entry);
	if (providedCek !== void 0 && !transport) throw new TypeError(`setContentEncryptionKey cannot be called with JWE "alg" (Algorithm) Header ${alg}`);
	let key = await prepareKey(mode === "direct-encryption" ? enc : entry, inputKey, "encrypt");
	if (mode === "direct-encryption") return [
		key,
		void 0,
		void 0
	];
	const cek = transport ? providedCek ?? generateCek(enc) : void 0;
	cek && checkCekLength(cek, enc.cekBits);
	let encryptedKey, parameters;
	switch (entry.subtle.name) {
		case "ECDH": {
			assertEcdhKey(key);
			const { apu: providedApu, apv: providedApv } = providedParameters;
			providedApu !== void 0 && assertUint8Array(providedApu, "\"apu\""), providedApv !== void 0 && assertUint8Array(providedApv, "\"apv\"");
			const apu = providedApu ?? partyInfo(joseHeader, "apu"), apv = providedApv ?? partyInfo(joseHeader, "apv");
			checkPartyInfo(apu, apv);
			let ephemeralKey;
			providedParameters.epk !== void 0 ? ephemeralKey = await prepareKey(entry, providedParameters.epk, "decrypt") : ephemeralKey = (await crypto.subtle.generateKey(key.algorithm, !0, ["deriveBits"])).privateKey;
			const subtle = crypto.subtle;
			let exportableEpk = ephemeralKey;
			if (!exportableEpk.extractable) {
				if (typeof subtle.getPublicKey != "function") throw new TypeError("CryptoKey for \"epk\" must be extractable");
				exportableEpk = await subtle.getPublicKey(ephemeralKey, []);
			}
			const { x, y, crv, kty } = await subtle.exportKey("jwk", exportableEpk), direct = mode === "direct-key-agreement", sharedSecret = await ecdhesDeriveKey(key, ephemeralKey, direct ? enc.alg : alg, direct ? enc.cekBits : parseInt(alg.slice(-5, -2), 10), apu, apv), epk = {
				x,
				crv,
				kty
			};
			if (kty === "EC" && (epk.y = y), parameters = { epk }, providedApu !== void 0 && (parameters.apu = encode$1(providedApu)), providedApv !== void 0 && (parameters.apv = encode$1(providedApv)), direct) return [
				sharedSecret,
				void 0,
				parameters
			];
			key = sharedSecret;
			break;
		}
		case "RSA-OAEP":
			assertCryptoKey(key), checkRsaKey(alg, key, "encrypt"), encryptedKey = new Uint8Array(await crypto.subtle.encrypt("RSA-OAEP", key, cek));
			break;
		case "PBKDF2": {
			const { p2c = 2048, p2s = crypto.getRandomValues(/* @__PURE__ */ new Uint8Array(16)) } = providedParameters;
			key = await deriveKey(p2s, alg, p2c, key), parameters = {
				p2c,
				p2s: encode$1(p2s)
			};
			break;
		}
		case "AES-GCM": {
			const iv = providedParameters.iv === void 0 ? crypto.getRandomValues(/* @__PURE__ */ new Uint8Array(12)) : providedParameters.iv;
			if (!(iv instanceof Uint8Array)) throw new TypeError("\"iv\" must be an instance of Uint8Array");
			const wrapped = await encrypt(jweEncryption(alg.slice(0, -2)), cek, key, iv, /* @__PURE__ */ new Uint8Array());
			encryptedKey = wrapped.ciphertext, parameters = {
				iv: encode$1(wrapped.iv),
				tag: encode$1(wrapped.tag)
			};
		}
	}
	if (encryptedKey ??= await aeskwWrap(alg.slice(-6), key, cek), !(encryptedKey instanceof Uint8Array) || !encryptedKey.byteLength) throw new TypeError("JWE key management algorithm did not produce an Encrypted Key");
	return [
		cek,
		encryptedKey,
		parameters
	];
}
//#endregion
//#region node_modules/jose/dist/webapi/lib/deflate.js
function validateZip(joseHeader, protectedHeader) {
	if (joseHeader.zip !== void 0 && joseHeader.zip !== "DEF") throw new JOSENotSupported("Unsupported JWE \"zip\" (Compression Algorithm) Header Parameter value.");
	if (joseHeader.zip !== void 0 && !protectedHeader?.zip) throw new JWEInvalid("JWE \"zip\" (Compression Algorithm) Header Parameter MUST be in a protected header.");
}
function supported(name) {
	if (typeof globalThis[name] > "u") throw new JOSENotSupported(`JWE "zip" (Compression Algorithm) Header Parameter requires the ${name} API.`);
}
async function transform(stream, input, maxLength = 1 / 0) {
	const writer = stream.writable.getWriter();
	writer.write(input).catch(() => {}), writer.close().catch(() => {});
	const chunks = [];
	let length = 0;
	const reader = stream.readable.getReader();
	for (;;) {
		const { value, done } = await reader.read();
		if (done) break;
		if (chunks.push(value), length += value.byteLength, maxLength !== 1 / 0 && length > maxLength) throw new JWEInvalid("Decompressed plaintext exceeded the configured limit");
	}
	return concat(...chunks);
}
async function compress(input) {
	return supported("CompressionStream"), transform(new CompressionStream("deflate-raw"), input);
}
async function decompress(input, maxLength) {
	return supported("DecompressionStream"), transform(new DecompressionStream("deflate-raw"), input, maxLength);
}
//#endregion
//#region node_modules/jose/dist/webapi/lib/jwe_decrypt.js
function shareJWE(jwe) {
	const { protected: encodedProtected, ciphertext, iv, tag, aad } = jwe;
	let parsedProt;
	return encodedProtected !== void 0 && (parsedProt = parseJoseHeader(encodedProtected, JWEInvalid, "JWE Protected Header is invalid")), [
		parsedProt,
		decodeBase64url(ciphertext, "ciphertext", JWEInvalid),
		iv !== void 0 ? decodeBase64url(iv, "iv", JWEInvalid) : void 0,
		tag !== void 0 ? decodeBase64url(tag, "tag", JWEInvalid) : void 0,
		encodeBase64url((encodedProtected ?? "") + (aad !== void 0 ? `.${aad}` : ""), "aad", JWEInvalid)
	];
}
function prepareDecrypt(options) {
	return [
		options && validateAlgorithms("keyManagementAlgorithms", options.keyManagementAlgorithms),
		options && validateAlgorithms("contentEncryptionAlgorithms", options.contentEncryptionAlgorithms),
		options?.crit,
		options?.maxPBES2Count,
		options?.maxDecompressedLength
	];
}
async function decryptJWE(jwe, shared, key, token = shareJWE(jwe)) {
	const [parsedProt, ciphertext, iv, tag, additionalData] = token, { header, unprotected, aad } = jwe;
	let joseHeader;
	if (header !== void 0 || unprotected !== void 0) {
		if (!isDisjoint(parsedProt, header, unprotected)) throw new JWEInvalid("JWE Protected, JWE Unprotected Header, and JWE Per-Recipient Unprotected Header Parameter names must be disjoint");
		joseHeader = {
			...parsedProt,
			...header,
			...unprotected
		};
	} else joseHeader = parsedProt ?? {};
	const [keyManagementAlgorithms, contentEncryptionAlgorithms, crit, maxPBES2Count, maxDecompressedLength] = shared, { encrypted_key: encodedKey } = jwe;
	validateCrit(JWEInvalid, JWE_RECOGNIZED, crit, parsedProt, joseHeader), validateZip(joseHeader, parsedProt);
	const { alg, enc } = joseHeader;
	if (typeof alg != "string" || !alg) throw new JWEInvalid("missing JWE Algorithm (alg) in JWE Header");
	const selected = JWE[alg];
	if (encodedKey === "" && (!selected || !isJWECEKTransport(selected))) throw new JWEInvalid("JWE Encrypted Key incorrect type");
	const integrated = selected?.mode === "integrated-encryption";
	if (!integrated && (typeof enc != "string" || !enc)) throw new JWEInvalid("missing JWE Encryption Algorithm (enc) in JWE Header");
	if (keyManagementAlgorithms && !keyManagementAlgorithms.has(alg) || !keyManagementAlgorithms && alg.startsWith("PBES2")) throw new JOSEAlgNotAllowed("\"alg\" (Algorithm) Header Parameter value not allowed");
	let encEntry;
	if (integrated) {
		if (enc !== void 0) throw new JWEInvalid("JWE \"enc\" (Encryption Algorithm) Header Parameter must not be present for integrated encryption");
		if (iv?.byteLength) throw new JWEInvalid("JWE Initialization Vector must be empty for integrated encryption");
		if (tag?.byteLength) throw new JWEInvalid("JWE Authentication Tag must be empty for integrated encryption");
	} else {
		if (contentEncryptionAlgorithms && !contentEncryptionAlgorithms.has(enc)) throw new JOSEAlgNotAllowed("\"enc\" (Encryption Algorithm) Header Parameter value not allowed");
		encEntry = jweEncryption(enc);
	}
	let encryptedKey;
	if (encodedKey !== void 0) try {
		encryptedKey = decodeBase64url(encodedKey, "encrypted_key", JWEInvalid);
	} catch (error) {
		if (!selected || !isJWECEKTransport(selected)) throw error;
		encryptedKey = /* @__PURE__ */ new Uint8Array();
	}
	let resolvedKey = !1;
	typeof key == "function" && (key = await key(parsedProt, jwe), resolvedKey = !0);
	const algEntry = selected ?? jweAlgorithm(alg);
	isJWECEKTransport(algEntry) && encryptedKey === void 0 && (encryptedKey = /* @__PURE__ */ new Uint8Array());
	const k = await prepareKey(algEntry.mode === "direct-encryption" ? encEntry : algEntry, key, "decrypt");
	let plaintext;
	if (algEntry.mode === "integrated-encryption") plaintext = await algEntry.decrypt(k, encryptedKey, ciphertext, additionalData, parsedProt, joseHeader);
	else {
		const encryption = encEntry;
		let cek;
		try {
			cek = await decryptKeyManagement(algEntry, encryption, k, encryptedKey, joseHeader, maxPBES2Count), isJWECEKTransport(algEntry) && cek instanceof Uint8Array && cek.byteLength << 3 !== encryption.cekBits && (cek = generateCek(encryption));
		} catch (err) {
			if (err instanceof TypeError || err instanceof JWEInvalid || err instanceof JOSENotSupported) throw err;
			cek = generateCek(encryption);
		}
		plaintext = await decrypt(encryption, cek, ciphertext, iv, tag, additionalData);
	}
	if (joseHeader.zip === "DEF") {
		const decompressionLimit = maxDecompressedLength ?? 25e4;
		if (decompressionLimit === 0) throw new JOSENotSupported("JWE \"zip\" (Compression Algorithm) Header Parameter is not supported.");
		if (decompressionLimit !== 1 / 0 && (!Number.isSafeInteger(decompressionLimit) || decompressionLimit < 1)) throw new TypeError("maxDecompressedLength must be 0, a positive safe integer, or Infinity");
		plaintext = await decompress(plaintext, decompressionLimit).catch((cause) => {
			throw cause instanceof JWEInvalid ? cause : new JWEInvalid("Failed to decompress plaintext", { cause });
		});
	}
	return {
		plaintext,
		...parsedProt && { protectedHeader: parsedProt },
		...aad !== void 0 && { additionalAuthenticatedData: decodeBase64url(aad, "aad", JWEInvalid) },
		...unprotected && { sharedUnprotectedHeader: unprotected },
		...header && { unprotectedHeader: header },
		...resolvedKey && { key: k }
	};
}
async function decryptCompact(jwe, shared, key) {
	if (jwe instanceof Uint8Array && (jwe = decoder.decode(jwe)), typeof jwe != "string") throw new JWEInvalid("Compact JWE must be a string or Uint8Array");
	const { 0: protectedHeader, 1: encryptedKey, 2: iv, 3: ciphertext, 4: tag, length } = jwe.split(".");
	if (length !== 5) throw new JWEInvalid("Invalid Compact JWE");
	return decryptJWE({
		ciphertext,
		iv: iv || void 0,
		protected: protectedHeader,
		tag: tag || void 0,
		encrypted_key: encryptedKey || void 0
	}, shared, key);
}
//#endregion
//#region node_modules/jose/dist/webapi/lib/jwe_encrypt.js
function checkDisjoint(protectedHeader, unprotectedHeader, sharedUnprotectedHeader) {
	if (!isDisjoint(protectedHeader, unprotectedHeader, sharedUnprotectedHeader)) throw new JWEInvalid("JWE Protected, JWE Shared Unprotected and JWE Per-Recipient Header Parameter names must be disjoint");
}
function checkEncryptHeaders(input, options, sharedHeadersNormalized = !1) {
	if (!input[1] && !input[2] && !input[3]) throw new JWEInvalid("either setProtectedHeader, setUnprotectedHeader, or sharedUnprotectedHeader must be called before #encrypt()");
	options !== void 0 && (input[8] = options?.crit);
	let [, protectedHeader, unprotectedHeader, sharedUnprotectedHeader, aad, cek, iv, keyManagementParameters, crit] = input;
	if (aad !== void 0 && assertUint8Array(aad, "JWE Additional Authenticated Data"), cek !== void 0 && assertUint8Array(cek, "JWE Content Encryption Key"), iv !== void 0 && assertUint8Array(iv, "JWE Initialization Vector"), !sharedHeadersNormalized && protectedHeader !== void 0 && (protectedHeader = serializeJoseHeader(JWEInvalid, protectedHeader)[0], input[1] = protectedHeader), unprotectedHeader !== void 0 && (unprotectedHeader = serializeJoseHeader(JWEInvalid, unprotectedHeader)[0], input[2] = unprotectedHeader), !sharedHeadersNormalized && sharedUnprotectedHeader !== void 0 && (sharedUnprotectedHeader = serializeJoseHeader(JWEInvalid, sharedUnprotectedHeader)[0], input[3] = sharedUnprotectedHeader), keyManagementParameters !== void 0 && !isObject(keyManagementParameters)) throw new TypeError("JWE Key Management Parameters must be an object");
	checkDisjoint(protectedHeader, unprotectedHeader, sharedUnprotectedHeader);
	const joseHeader = {
		...protectedHeader,
		...unprotectedHeader,
		...sharedUnprotectedHeader
	};
	validateCritDuplicates(JWEInvalid, protectedHeader), validateCrit(JWEInvalid, JWE_RECOGNIZED, crit, protectedHeader, joseHeader), validateZip(joseHeader, protectedHeader);
	const { alg, enc } = joseHeader;
	if (typeof alg != "string" || !alg) throw new JWEInvalid("JWE \"alg\" (Algorithm) Header Parameter missing or invalid");
	const algEntry = JWE[alg];
	if (algEntry?.mode === "integrated-encryption") {
		if (enc !== void 0) throw new JWEInvalid("JWE \"enc\" (Encryption Algorithm) Header Parameter must not be present for integrated encryption");
		if (cek !== void 0) throw new TypeError(`setContentEncryptionKey cannot be called with JWE "alg" (Algorithm) Header ${alg}`);
		if (iv !== void 0) throw new TypeError(`setInitializationVector cannot be called with JWE "alg" (Algorithm) Header ${alg}`);
		return [
			joseHeader,
			void 0,
			algEntry
		];
	}
	if (typeof enc != "string" || !enc) throw new JWEInvalid("JWE \"enc\" (Encryption Algorithm) Header Parameter missing or invalid");
	return [
		joseHeader,
		jweEncryption(enc),
		algEntry
	];
}
async function encryptJWE(input, checked, key) {
	const [joseHeader, encEntry, selected] = checked, [inputPlaintext, inputProtectedHeader, inputUnprotectedHeader, sharedUnprotectedHeader, aad, providedCek, inputIv, keyManagementParameters, , unprotectedParameters] = input;
	let protectedHeader = inputProtectedHeader, unprotectedHeader = inputUnprotectedHeader;
	const algEntry = selected ?? jweAlgorithm(joseHeader.alg);
	let encryptedKey, parameters, cek;
	algEntry.mode === "integrated-encryption" ? cek = await prepareKey(algEntry, key, "encrypt") : [cek, encryptedKey, parameters] = await encryptKeyManagement(algEntry, encEntry, key, joseHeader, providedCek, keyManagementParameters), parameters && (unprotectedParameters ? unprotectedHeader = unprotectedHeader ? {
		...unprotectedHeader,
		...parameters
	} : parameters : protectedHeader = protectedHeader ? {
		...protectedHeader,
		...parameters
	} : parameters, checkDisjoint(protectedHeader, unprotectedHeader, sharedUnprotectedHeader));
	const protectedHeaderS = protectedHeader ? encode$1(JSON.stringify(protectedHeader)) : "", aadMember = aad?.byteLength ? encode$1(aad) : void 0, additionalData = encode(aadMember ? `${protectedHeaderS}.${aadMember}` : protectedHeaderS);
	let plaintext = inputPlaintext;
	joseHeader.zip === "DEF" && (plaintext = await compress(plaintext).catch((cause) => {
		throw new JWEInvalid("Failed to compress plaintext", { cause });
	}));
	let ciphertext, tag, iv;
	algEntry.mode === "integrated-encryption" ? [encryptedKey, ciphertext] = await algEntry.encrypt(cek, plaintext, additionalData, protectedHeader, joseHeader, keyManagementParameters) : {ciphertext, tag, iv} = await encrypt(encEntry, plaintext, cek, inputIv, additionalData);
	const jwe = { ciphertext: encode$1(ciphertext) };
	return iv && (jwe.iv = encode$1(iv)), tag && (jwe.tag = encode$1(tag)), encryptedKey?.byteLength && (jwe.encrypted_key = encode$1(encryptedKey)), aadMember && (jwe.aad = aadMember), protectedHeader && (jwe.protected = protectedHeaderS), sharedUnprotectedHeader && (jwe.unprotected = sharedUnprotectedHeader), unprotectedHeader && (jwe.header = unprotectedHeader), jwe;
}
async function createJWE(input, key, options) {
	return encryptJWE(input, checkEncryptHeaders(input, options), key);
}
function compactJWE(jwe) {
	return [
		jwe.protected,
		jwe.encrypted_key,
		jwe.iv,
		jwe.ciphertext,
		jwe.tag
	].join(".");
}
//#endregion
//#region node_modules/jose/dist/webapi/jwt/decrypt.js
async function jwtDecrypt(jwt, key, options) {
	const { plaintext, ...result } = await decryptCompact(jwt, prepareDecrypt(options), key), { protectedHeader } = result, payload = validateClaimsSet(protectedHeader, plaintext, options);
	for (const claim of [
		"iss",
		"sub",
		"aud"
	]) if (protectedHeader[claim] !== void 0 && (claim === "aud" ? JSON.stringify(protectedHeader.aud) !== JSON.stringify(payload.aud) : protectedHeader[claim] !== payload[claim])) throw new JWTClaimValidationFailed(`replicated "${claim}" claim header parameter mismatch`, payload, claim, "mismatch");
	return {
		payload,
		...result
	};
}
//#endregion
//#region node_modules/jose/dist/webapi/lib/jws_sign.js
async function createSignature(input, key, rejectUnencoded) {
	let [payload, protectedHeader, unprotectedHeader, crit] = input, protectedHeaderString = "";
	if (protectedHeader !== void 0) {
		const normalized = serializeJoseHeader(JWSInvalid, protectedHeader);
		protectedHeader = normalized[0], protectedHeaderString = encode$1(normalized[1]);
	}
	if (unprotectedHeader !== void 0 && (unprotectedHeader = serializeJoseHeader(JWSInvalid, unprotectedHeader)[0]), !protectedHeader && !unprotectedHeader) throw new JWSInvalid("either setProtectedHeader or setUnprotectedHeader must be called before #sign()");
	if (!isDisjoint(protectedHeader, unprotectedHeader)) throw new JWSInvalid("JWS Protected and JWS Unprotected Header Parameter names must be disjoint");
	const joseHeader = {
		...protectedHeader,
		...unprotectedHeader
	};
	validateCritDuplicates(JWSInvalid, protectedHeader);
	const b64 = validateB64(protectedHeader, validateCrit(JWSInvalid, JWS_RECOGNIZED, crit, protectedHeader, joseHeader));
	b64 || rejectUnencoded?.();
	const { alg } = joseHeader;
	if (typeof alg != "string" || !alg) throw new JWSInvalid("JWS \"alg\" (Algorithm) Header Parameter missing or invalid");
	const entry = jwsAlgorithm(alg);
	let payloadS = "", payloadB = payload, data;
	if (b64) {
		const encoded = input[4];
		encoded ? (payloadS = encoded[0] ??= encode$1(payload), payloadB = encoded[1] ??= encode(payloadS)) : (payloadS = encode$1(payload), data = encoder.encode(`${protectedHeaderString}.${payloadS}`));
	}
	data ??= concat(encode(protectedHeaderString), encode("."), payloadB);
	const k = await rawKey(await prepareKey(entry, key, "sign"), entry.subtle, "sign");
	entry.minRsaBits && checkModulusLength(entry.alg, k);
	const jws = {
		signature: encode$1(new Uint8Array(await crypto.subtle.sign(entry.signing, k, data))),
		payload: payloadS
	};
	return protectedHeader && (jws.protected = protectedHeaderString), unprotectedHeader && (jws.header = unprotectedHeader), [jws, b64];
}
async function createCompactSignature(payload, protectedHeader, crit, key, rejectUnencoded) {
	const [jws] = await createSignature([
		payload,
		protectedHeader,
		void 0,
		crit
	], key, rejectUnencoded);
	return `${jws.protected}.${jws.payload}.${jws.signature}`;
}
//#endregion
//#region node_modules/jose/dist/webapi/jwt/sign.js
var SignJWT_base = JWTClaimsBuilder;
var SignJWT = class extends SignJWT_base {
	#protectedHeader;
	setProtectedHeader(protectedHeader) {
		return assertNotSet(this.#protectedHeader, "setProtectedHeader"), this.#protectedHeader = protectedHeader, this;
	}
	async sign(key, options) {
		return createCompactSignature(jwtData(this), this.#protectedHeader, options?.crit, key, () => {
			throw new JWTInvalid("JWTs MUST NOT use unencoded payload");
		});
	}
};
//#endregion
//#region node_modules/jose/dist/webapi/jwt/encrypt.js
var EncryptJWT_base = JWTClaimsBuilder;
var EncryptJWT = class extends EncryptJWT_base {
	#input = [void 0];
	#replicateIssuerAsHeader;
	#replicateSubjectAsHeader;
	#replicateAudienceAsHeader;
	setProtectedHeader(protectedHeader) {
		return assertNotSet(this.#input[1], "setProtectedHeader"), this.#input[1] = protectedHeader, this;
	}
	setKeyManagementParameters(parameters) {
		return assertNotSet(this.#input[7], "setKeyManagementParameters"), this.#input[7] = parameters, this;
	}
	setContentEncryptionKey(cek) {
		return assertNotSet(this.#input[5], "setContentEncryptionKey"), this.#input[5] = cek, this;
	}
	setInitializationVector(iv) {
		return assertNotSet(this.#input[6], "setInitializationVector"), this.#input[6] = iv, this;
	}
	replicateIssuerAsHeader() {
		return this.#replicateIssuerAsHeader = !0, this;
	}
	replicateSubjectAsHeader() {
		return this.#replicateSubjectAsHeader = !0, this;
	}
	replicateAudienceAsHeader() {
		return this.#replicateAudienceAsHeader = !0, this;
	}
	async encrypt(key, options) {
		const plaintext = jwtData(this);
		this.#input[1] && (this.#replicateIssuerAsHeader || this.#replicateSubjectAsHeader || this.#replicateAudienceAsHeader) && (this.#input[1] = {
			...this.#input[1],
			iss: this.#replicateIssuerAsHeader ? jwtClaim(this, "iss") : void 0,
			sub: this.#replicateSubjectAsHeader ? jwtClaim(this, "sub") : void 0,
			aud: this.#replicateAudienceAsHeader ? jwtClaim(this, "aud") : void 0
		});
		const input = [...this.#input];
		return input[0] = plaintext, compactJWE(await createJWE(input, key, options));
	}
};
//#endregion
//#region node_modules/jose/dist/webapi/key/export.js
async function exportJWK(key) {
	if (isKeyObject(key)) if (key.type === "secret") key = key.export();
	else return key.export({ format: "jwk" });
	if (key instanceof Uint8Array) return {
		kty: "oct",
		k: encode$1(key)
	};
	if (!isCryptoKey(key)) throw new TypeError(invalidKeyInput(key, "CryptoKey", "KeyObject", "Uint8Array"));
	if (!key.extractable) throw new TypeError("non-extractable CryptoKey cannot be exported as a JWK");
	const jwk = await crypto.subtle.exportKey("jwk", key);
	delete jwk.ext, delete jwk.key_ops, delete jwk.use, jwk.kty !== "AKP" && delete jwk.alg;
	for (const parameter of Object.keys(jwk)) jwk[parameter] === void 0 && delete jwk[parameter];
	return jwk;
}
//#endregion
//#region node_modules/jose/dist/webapi/jwk/thumbprint.js
var check = (value, description) => {
	if (typeof value != "string" || !value) throw new JWKInvalid(`${description} missing or invalid`);
};
async function calculateJwkThumbprint(key, digestAlgorithm) {
	let jwk;
	if (isObject(key)) {
		if (jwk = snapshotJwk(key), typeof jwk.kty != "string") throw new TypeError(invalidKeyInput(key, "CryptoKey", "KeyObject", "JSON Web Key"));
	} else if (isKeyLike(key)) jwk = snapshotJwk(await exportJWK(key));
	else throw new TypeError(invalidKeyInput(key, "CryptoKey", "KeyObject", "JSON Web Key"));
	if (digestAlgorithm ??= "sha256", digestAlgorithm !== "sha256" && digestAlgorithm !== "sha384" && digestAlgorithm !== "sha512") throw new TypeError("digestAlgorithm must one of \"sha256\", \"sha384\", or \"sha512\"");
	let components;
	switch (jwk.kty) {
		case "AKP":
			check(jwk.alg, "\"alg\" (Algorithm) Parameter"), check(jwk.pub, "\"pub\" (Public key) Parameter"), components = {
				alg: jwk.alg,
				kty: jwk.kty,
				pub: jwk.pub
			};
			break;
		case "EC":
			check(jwk.crv, "\"crv\" (Curve) Parameter"), check(jwk.x, "\"x\" (X Coordinate) Parameter"), check(jwk.y, "\"y\" (Y Coordinate) Parameter"), components = {
				crv: jwk.crv,
				kty: jwk.kty,
				x: jwk.x,
				y: jwk.y
			};
			break;
		case "OKP":
			check(jwk.crv, "\"crv\" (Subtype of Key Pair) Parameter"), check(jwk.x, "\"x\" (Public Key) Parameter"), components = {
				crv: jwk.crv,
				kty: jwk.kty,
				x: jwk.x
			};
			break;
		case "RSA":
			check(jwk.e, "\"e\" (Exponent) Parameter"), check(jwk.n, "\"n\" (Modulus) Parameter"), components = {
				e: jwk.e,
				kty: jwk.kty,
				n: jwk.n
			};
			break;
		case "oct":
			if (typeof jwk.k != "string") throw new JWKInvalid("\"k\" (Key Value) Parameter missing or invalid");
			components = {
				k: jwk.k,
				kty: jwk.kty
			};
			break;
		default: throw new JOSENotSupported("\"kty\" (Key Type) Parameter missing or unsupported");
	}
	const data = encode(JSON.stringify(components));
	return encode$1(await digest(digestAlgorithm, data));
}
//#endregion
export { EncryptJWT, SignJWT, calculateJwkThumbprint, jwtDecrypt };
