# VHF Toroid Core Data

This page is an appendix to [Component Data Sources](component-data-sources.md#vhf-iron-powder-toroids-mixes-0-10-17).
It records every Micrometals part datasheet examined for iron-powder mixes 0, 10 and 17, as
evidence for the decision not to offer VHF toroids. No calculator output uses these values.

- **Source.** Each row is the Micrometals part datasheet at
  `https://datasheets.micrometals.com/<core>-DataSheet.pdf`, page 1, retrieved 2026-11-19.
  The SHA-256 identifies the copy that was read; the revision is the one the sheet prints.
- **A_L** is the sheet's "AL value (nominal)" in nH/turn².
- **Guarantee type** is the sheet's "AL tolerance" wording. Mix 0 prints "Ref Only"
  (reference-only). Mixes 10 and 17 print "±5%", which the 2023 catalog labels "Typical"
  (see the main page). No sheet publishes an SRF, self-resonance or winding capacitance.
- **A_L test** is the sheet's test winding, test frequency and "Voltage on Agilent 4284A".
  The tolerance applies only to that winding.

| Core | A_L (nH/turn²) | A_L tolerance | A_L test (winding; frequency; voltage) | Revision | SHA-256 |
|---|---|---|---|---|---|
| T5-0 | 0.16 | Ref Only | N/A | 20190524 | b671a4193d16b881fc8e767b2921002145f9d8a8eee02080f6fd3324b179aeb2 |
| T7-0 | 0.3 | Ref Only | N/A | 20190524 | aec0ecf6bbba1816c8d624e3de4d2ffb812aea4915eaa4c44c39b84b9aa67bd5 |
| T10-0 | 0.24 | Ref Only | N/A | 20190524 | 395fd9dbbe0bb04313e97edf29177799e040fb990cf94c07da096c97453da0d9 |
| T12-0 | 0.24 | Ref Only | N/A | 2022-Jun-02 | c07e697270f3e6be0f43beb01f665bd504038a9b65df0785b93a969e720c68ad |
| T12-0A | 0.13 | Ref Only | N/A | 2022-Jun-02 | 1ee783c807c0d88f290649b66f1e94aeed7c2e6e4978eeb2c38f4fba9b36f30d |
| T16-0 | 0.3 | Ref Only | N/A | 2022-Jun-02 | 1d2c07ad8b5f71555464a46bdb723baa43b1517a87c3f72b21f069bbbc439857 |
| T16-0D | 0.3 | Ref Only | N/A | 2022-Jun-02 | a95aac2d477f3ab01540abb8cb67bc71388bbe81217e2cac5f5522c6c263357b |
| T20-0 | 0.35 | Ref Only | N/A | 2022-Jun-02 | 5d9859198bfa283fef815544595889110dac6b1c1f95d9994510811904791da4 |
| T20-0D | 0.35 | Ref Only | N/A | 2022-Jun-02 | 20226edfe8572b8fde10004fade657757ce914a160fe25bafb28535c9d6dad6e |
| T20-0F | 0.48 | Ref Only | N/A | 2022-Jun-02 | e3790949e3b226de9ee188c9b18f6614b28fae0fd639060731ba43a8b2a8798a |
| T22-0 | 0.71 | Ref Only | N/A | 20190524 | 284d610d23f5d455ae5775e76922aec8ccd6e1c691348a9d389e8748f6f7ac20 |
| T22-0A | 0.51 | Ref Only | N/A | 20190524 | 2658bca474064394ead1762daaccb510a8bfcdea964e3f43f9e667ef45b0e4a9 |
| T25-0 | 0.45 | Ref Only | N/A | 20190524 | de8c8e1122f70b3c916605d2412aee6377eb944c449466260f5f21df96443e6c |
| T25-0D | 0.9 | Ref Only | N/A | 20190524 | 12cd89aa75c4901b239ad94aed41030b2df44e0267e74ebfb48cb0757d5ed192 |
| T27-0 | 0.45 | Ref Only | N/A | 20190524 | 41d1abb782121c6b8919d9ce593d86fb2463aff1f20e2da79c26d0d3dfedffdf |
| T30-0 | 0.6 | Ref Only | N/A | 20190524 | 6247f63d8db967c5be0642d7d5b36afb33eef3423bff220407f61f5bd9fdaeca |
| T37-0 | 0.49 | Ref Only | N/A | 20190524 | 235cee3784c40cfc6be87801309c2053b562e03c1a3462fdebdce4c1b0a5d7d7 |
| T44-0 | 0.65 | Ref Only | N/A | 20190524 | 3fa9bb1725d3ddade4cae82a2452bfcc21279ede12cbb58fc5519fc8885fcc98 |
| T44-0D | 1.4 | Ref Only | N/A | 20190524 | 74e0a4a64d76da55b72991b347444189a5523b96d8a28599544efe73417fc473 |
| T50-0 | 0.64 | Ref Only | N/A | 20190524 | cfb6098d5b05d061ca064bba44c4bd266cd586c0289a2bf7098fe9617a988a09 |
| T51-0 | 2.6 | Ref Only | N/A | 20200518 | fcaffb321b9bede6de4a8f4a1d144bcd8a412c4a9137d10347176683aea95d98 |
| T60-0 | 0.88 | Ref Only | N/A | 20190524 | 88fc1431d4e1b0ed49aba49d517ae7178e0ddff05ab71ced9854ff6ad0612e0f |
| T68-0 | 0.75 | Ref Only | N/A | 20190524 | c603168974e10de4b160235012303fd4e2a9270b569009c26266d2b877635326 |
| T72-0 | 1.5 | Ref Only | N/A | 20190524 | 22ba6bcf952abb640b5b1f0e0cc52c92dfd8d572b4f9584bf0c2192d2b461e0b |
| T80-0 | 0.85 | Ref Only | N/A | 20190524 | 760fb14d1e95edd1672b5f482053e281cc50819eca6095637f9d0a756795d6a7 |
| T94-0 | 1.06 | Ref Only | N/A | 20190524 | ebb2b3fe9f4df9fecc71f675d9b536e72fa64cb1739c8842167b355ade85e948 |
| T106-0 | 1.9 | Ref Only | N/A | 20190524 | 5b314307ae36d50e52e5911a3938afefec91d76f910655f9af7be7b4fbdfffaa |
| T130-0 | 1.5 | Ref Only | N/A | 20190524 | 62f55d0ff8b94a88c90622478ff10abbf33bba04061914bde5db8b89a7b80a57 |
| T157-0 | 1.8 | Ref Only | N/A | 20190524 | 501c916e44e1f6ca514bed967ac51fa1248db9806b4fff766a9eae86d8d36237 |
| T184-0 | 3 | Ref Only | N/A | 20190524 | 4886aab2665b5bc86341d1a8fdc84eb54fd696af631c379682167b465b88bc7c |
| T201-0 | 4.2 | Ref Only | N/A | 20200518 | de6957beaeb447c2ba37b726ef4424ba90eb57cb9327ccd023b2ab346478bed5 |
| T300-0 | 1.5 | Ref Only | N/A | 20190524 | 0121f01bb9176f9f12015d78732d4b7e5cfc35ca23fb1b321821df30170a48fd |
| T400-0 | 2.4 | Ref Only | N/A | 20190524 | 3626b044bee5cd448958ae337f8a26ab28ce5bdb75227a090a400f42f32463a6 |
| T400-0D | 4.8 | Ref Only | N/A | 20190524 | 1039ff709347af846219f6e85aa828818969a5050c8b18a907d69ee249a2dfc2 |
| T5-10 | 0.7 | ±5% | N=15, #40 AWG; 1 MHz; 0.013 V | 20200518 | 984a2add68fdc31f44bc15fefe3c2a2d82322bfd3e781f5d8f651c85ab20ab87 |
| T7-10 | 0.9 | ±5% | N=10, #36 AWG; 1 MHz; 0.016 V | 20200518 | 8c549b9d8bc4301448ecd2ba67b33f12b572225bf8d267f5a8f445fa196f328f |
| T10-10 | 0.8 | ±5% | N=25, #40 AWG; 1 MHz; 0.050 V | 20200518 | ccb97cdd7c431c321c8299919255075ee2c5db958b1e04399a05274e5099c5aa |
| T10-10B | 1.25 | ±5% | N=25, #40 AWG; 1 MHz; 0.083 V | 2025-Apr-9 | f4d56e77ca5955ad2c9b7ae5679df8881b887044d7e1aa141d3a60d6897da36c |
| T12-10 | 1.2 | ±5% | N=25, #36 AWG; 1 MHz; 0.11 V | 20200518 | 862124c1992b52d2d3847de00dec96320a48b39505f6d69d3e384e1576a02e3b |
| T12-10A | 0.72 | ±5% | N=25, #36 AWG; 1 MHz; 0.063 V | 2023-Dec-14 | dfd6fdf1450200c15f143b1b9cdd5e2bbbcdc4ed1f38748629710c42dbbc5588 |
| T12-10B | 1 | ±5% | N=25, #36 AWG; 1 MHz; 0.089 V | 20200518 | d82fffbd2599c7c5d1ad6743a27634160643d88fa4c15e8cab1f5c32eb7ed3c7 |
| T16-10 | 1.3 | ±5% | N=40, #36 AWG; 1 MHz; 0.27 V | 20200518 | ead950baeb1d5a572057280940a5f155f19250d8ac43c49b7194aafe4a4e04e6 |
| T20-10 | 1.6 | ±5% | N=50, #36 AWG; 1 MHz; 0.51 V | 20200518 | 627e3d670b87df3bb9c1c10868283f476ecde856968f08406e3a83bbc834ef09 |
| T22-10 | 3.2 | ±5% | N=50, #35 AWG; 1 MHz; 1.0 V | 20190524 | d09f6d1cf27213910a2085abbc59c9878bb83630bcf44e4b9265534b1a3f1741 |
| T22-10A | 2.2 | ±5% | N=50, #36 AWG; 1 MHz; 0.82 V | 2023-Dec-14 | 7d2c778433030625373036bcc1c8107665914dd9d6e0e00c1ee0768ecb212399 |
| T25-10 | 1.9 | ±5% | N=50, #34 AWG; 1 MHz; 0.82 V | 20190524 | 344c98c82a644617ebdcbb00671cfedea4412696db844c17a1baf33835d4dabc |
| T25-10A | 1.46 | ±5% | N=50, #34 AWG; 1 kHz; 0.0006 V | 20200721 | 29a8f0b525db514f38eb7ee7a090679b6e84a702b519c2662dc072406eaac549 |
| T27-10 | 2.2 | ±5% | N=50, #34 AWG; 1 MHz; 1.0 V | 20190524 | 3d20440a01f14253830fa49fa6d8733d47e870ec27ff9ef92cfefc5ef2573001 |
| T30-10 | 2.5 | ±5% | N=50, #32 AWG; 1 MHz; 1.0 V | 20190524 | 9c9423da688c679e199de0a1f709384b0f66b57240dc89f7745442548db3e8e2 |
| T37-10 | 2.5 | ±5% | N=50, #30 AWG; 1 MHz; 1.0 V | 20190524 | c7b37e23fbea837f2ba95df94d3122d72392454b4f734f53fdcceb75c4d6899b |
| T44-10 | 3.3 | ±5% | N=66, #30 AWG; 1 MHz; 1.0 V | 20190524 | 643c82174d6f62afb05b6930edf306b312095ac23220c0034815dcca90e38206 |
| T50-10 | 3.1 | ±5% | N=35, #24 AWG; 1 MHz; 1.0 V | 20190524 | 50a50664b2cedf39deced8557956e4b12eb918635ce88a0e68b759b722ca1b3d |
| T60-10 | 4 | ±5% | N=100, #32 AWG; 1 MHz; 1.0 V | 20190524 | a4248c18fef9f43caec45887167c321e2c3edc821ab3dddc93bf88e0f81f3bc0 |
| T68-10 | 3.2 | ±5% | N=100, #30 AWG; 1 MHz; 1.0 V | 20190524 | 77c088a4f04141debea8e7fe72060aeaf001917c9df5038e7435fbef9d75c0ba |
| T80-10 | 3.2 | ±5% | N=100, #28 AWG; 1 MHz; 1.0 V | 20190524 | b0c7660b6ec9067502e19547f39e5d655920edef88ca1f31452dc2004e123774 |
| T94-10 | 5.8 | ±5% | N=100, #28 AWG; 1 MHz; 1.0 V | 20190524 | fabc4a38b105d64b08e4fc6cbd5be6565d79d749e90dba4a8d08eac0ba4d0a62 |
| T106-10 | 8.5 | ±5% | N=100, #26 AWG; 1 MHz; 1.0 V | 2023-Dec-14 | adb82abb9eaa6cdce82b642ce1b6fcf8e878c8e320a4a2503df362135eec042c |
| T106-10B | 11.1 | ±5% | N=100, #26 AWG; 10 kHz; 0.38 V | 2023-Dec-14 | 271d78aeb3107184424df7a8954312baeb48889845b5ed199180a742bfe3b936 |
| T130-10 | 6.83 | ±5% | N=100, #24 AWG; 10 kHz; 0.31 V | 2023-Dec-14 | a0d7e98df894552627f44de049508f32648cf59bd1ab55a4d9e18007ab8dfe79 |
| T157-10 | 8.2 | ±5% | N=100, #24 AWG; 1 MHz; 1.0 V | 20190524 | e61c0d281d08b201cecc9f7d786beb94264bb6f4c683f0e4b52564ff5529925f |
| T184-10 | 13.8 | ±5% | N=100, #24 AWG; 10 kHz; 0.83 V | 2023-Dec-14 | 5926e1a14da5bda7f0638e7622ce8a2205fba1c2d142e4c0dd601c152539cb75 |
| T5-17 | 0.42 | ±5% | N=15, #40 AWG; 1 MHz; 0.013 V | 20200518 | 9a6d7b23fa3e62a05ad7328fc080f28f5535ccb78c276649bfd4e0dd543a9d07 |
| T7-17 | 0.6 | ±5% | N=10, #36 AWG; 1 MHz; 0.016 V | 20200518 | 328fb37a2c3bad284a960ffae0567add2863860bad961cb6808bdd210aab37bf |
| T10-17 | 0.5 | ±5% | N=25, #40 AWG; 1 MHz; 0.050 V | 20200518 | d919e7a1e2957604d95dd7d8720a5a95c29e288826571a6ccf46713e40d497d1 |
| T12-17 | 0.75 | ±5% | N=25, #36 AWG; 1 MHz; 0.11 V | 20200518 | 8248a1e56f6ded57206f8892ce6499292f641b8debdf2059d2ab0a4090c03df1 |
| T16-17 | 0.8 | ±5% | N=40, #36 AWG; 1 MHz; 0.27 V | 20200518 | dca543b1534606b678e8d38234ccf500bdd2b7e89731c531c81b6a38009a49d4 |
| T20-17 | 1 | ±5% | N=50, #36 AWG; 1 MHz; 0.51 V | 20200518 | f26deb6e4fff769d602f869412d193cc5462d7f2515fb86df53d612eba4bad01 |
| T22-17 | 2 | ±5% | N=50, #36 AWG; 1 MHz; 1.0 V | 20190524 | 4a7478ad398c742e264e17edc472f83767968b37bbd5c9ddb205415101c1dfd4 |
| T22-17A | N/A | N/A | N=50, #36 AWG; 1 MHz; N/A | 2023-Dec-14 | 8cc1074eeb19bb4944805e13341065b4d9183dc0b6e7a5ae4c37ce544b43e5e2 |
| T25-17 | 1.2 | ±5% | N=50, #34 AWG; 1 MHz; 0.82 V | 20190524 | 9f1e7ccd4eae2fc960b9ae6b122489233b9cfc48e5e309eb61368ac7bc8a8fbd |
| T27-17 | 1.3 | ±5% | N=50, #34 AWG; 1 MHz; 1.0 V | 20190524 | 58f0d949982c42f3c6a02bfd08dfb76a91a87fb1c735c730fbf92d84ac90709c |
| T30-17 | 1.6 | ±5% | N=37, #30 AWG; 1 MHz; 0.99 V | 20190524 | 7def56957e9bff70c40c347a3f0c64bfc58ee0faf0a6f8098dfeefc0d02fcac1 |
| T37-17 | 1.5 | ±5% | N=52, #30 AWG; 1 MHz; 1.0 V | 20190524 | 59817fc2b5709dce7e8882b27b531ba905fb4e94b642b3d1c6655a9d5381adac |
| T44-17 | 1.85 | ±5% | N=100, #34 AWG; 1 MHz; 1.0 V | 20190524 | 6360fe787d9033ad79751a0079bb60c9bc7bca24bc4d66d0cf57c315b27e2789 |
| T44-17D | 3.7 | ±5% | N=100, #34 AWG; 1 MHz; 1.0 V | 2023-Dec-14 | aa1e53d94a101d501c3ecd3b0a7058443055d4cd0d91a26e27fe6d6dca899bd6 |
| T50-17 | 1.8 | ±5% | N=100, #32 AWG; 1 MHz; 1.0 V | 20190524 | b0a48132910e8a7d070aad607f517ebfc984b3069b9663513bd72d09585e6f25 |
| T60-17 | 2.6 | ±5% | N=100, #32 AWG; 1 MHz; 1.0 V | 20190524 | 20ccddf1c07b3fcd83d77b65605a42b272c78ac748ab553419287f2cade394f0 |
| T68-17 | 2.1 | ±5% | N=100, #30 AWG; 1 MHz; 1.0 V | 20190524 | dab39f341bd2546f1a65ebf96527a81f9d484e76869da211849c592d84504588 |
| T68-17A | 2.8 | ±5% | N=100, #30 AWG; 1 MHz; 1.0 V | 20190524 | 60b6c719cbb9040317287f07a4d870e6f21ad4ded12580acb7008c9f048e7f2b |
| T68-17D | 4.2 | ±5% | N=100, #30 AWG; 1 MHz; 1.0 V | 20190524 | 5430217c6c6041e02147ba27ee60db052e5c326f1ff8310fa4f6790c5569f470 |
| T68-17E | 5.7 | ±5% | N=100, #30 AWG; 1 MHz; 1.0 V | 20190524 | eb49ca97116156c7ca30529c2a8cf936e62e2b0c55e059d9a78b7f1b51b4e997 |
| T72-17 | 4.5 | ±5% | N=50, #28 AWG; 1 MHz; 1.0 V | 2023-Dec-14 | 4f68bbaec9c48c8cc97a3e81d2eeed63474619d4842ee9e33c133e45f7752df7 |
| T80-17 | 2.2 | ±5% | N=100, #28 AWG; 1 MHz; 1.0 V | 20190524 | 09db56d176a361a7af027bd49c87ab9e6892737be6f8fc760faef186ef43efdb |
| T80-17D | 4.4 | ±5% | N=100, #28 AWG; 1 MHz; 1.0 V | 2023-Dec-14 | 0622be449854f45106239c8e09ae5a1842e717caa49676dc83bbe86acd9bb349 |
| T94-17 | 2.9 | ±5% | N=100, #28 AWG; 1 MHz; 1.0 V | 20190524 | 43e18e054291f610db9dab419a62d8fd5286dfd9f999da34144ab19efad313da |
| T106-17 | 5.1 | ±5% | N=100, #28 AWG; 1 MHz; 1.0 V | 20190524 | 7bdcbd4c926124a97037df0b936e15b40717554f4149e3c1feddaa254ba0a39f |
| T106-17B | 6.6 | ±5% | N=100, #28 AWG; 1 MHz; 1.0 V | 20190524 | 06a9f0f7272cc39f5724b11489673d2809bb539b44feabb41f2412c7fbcfb1c8 |
| T130-17 | 4 | ±5% | N=100, #24 AWG; 1 MHz; 1.0 V | 20190524 | 723e04d17c06df6dc62b4e3ad31261f78ff9cd73ca9e41b403efcfd868f53916 |
| T157-17 | 5.3 | ±5% | N=100, #24 AWG; 1 MHz; 1.0 V | 20190524 | b27bcaa5aa206913b2f8e1e55da26b0667a1ad809f4b72870724297ef80a41c3 |
| T184-17 | 8.7 | ±5% | N=100, #24 AWG; 1 MHz; 1.0 V | 20190524 | f5d400e7a0bb7d706af0ecae2efbbb7744a14ef2bb3a8ee09e5e087142921164 |
| T225-17 | 5 | ±5% | N=100, #22 AWG; 1 MHz; 1.0 V | 2023-Dec-14 | bdf8f3d59508ca2a6793d0fd427c1aa8ef3ff4b7d224fd334bd870e49fd51035 |
| T400-17D | 14.4 | ±5% | N=40, #20 AWG; 10 kHz; 0.14 V | 2023-Dec-14 | eb47881ee681a0b926d1b890284b7dfbb78238e41012054b15b70307a9820fab |

**T225-10** has no row: its datasheet URL was refused (HTTP 403), and it is absent from the 2023
catalog's toroid tables. The only value found is 7.5 nH/turn² in Micrometals' HTML product
finder (`https://new.micrometals.com/products/product-finder/`, mix -10, OD 30–200 mm; SHA-256
of the saved page 472087ca657aa38942c307a87239f297d69afb707f53628cfe14eccce7f162ba). That site
served an injected overlay on 2026-11-19, so the value is uncorroborated, its tolerance is
unverified, and it is not used.
