/**
 * 导出文本文件（当前只用于报表 CSV）。
 *
 * 策略（按可靠性排序）：
 *   1. 系统「文件另存」选择器（用户自己选位置，最符合预期）；
 *   2. 选择器不可用/被取消/写失败 → 回退写到应用沙箱 `filesDir`，并把路径显示出来。
 *
 * ⚠ 之前踩过 `fileIo.writeSync` 写入 0 字节的坑，所以这里每次写完都 stat 校验大小，
 *   不一致就报错，绝不假装成功。
 */

import { fileIo, picker } from '@kit.CoreFileKit';
import { common } from '@kit.AbilityKit';
import { util } from '@kit.ArkTS';
import { BusinessError } from '@kit.BasicServicesKit';

export class ExportResult {
  ok: boolean = false;
  /** 成功时是保存路径；失败时是原因。 */
  message: string = '';
  path: string = '';
  /** 是否写进了应用沙箱（picker 不可用时的回退）。 */
  sandbox: boolean = false;
}

function errText(e: Error): string {
  const be: BusinessError = e as BusinessError;
  const code: number | undefined = be === undefined ? undefined : be.code;
  const msg: string = (be === undefined || be.message === undefined) ? `${e}` : be.message;
  return code === undefined ? msg : `code=${code} ${msg}`;
}

/** 无状态的编码器，模块级复用。 */
const ENCODER: util.TextEncoder = new util.TextEncoder();

/** 写文本并校验落盘字节数；返回写入长度。 */
function writeTextSync(uri: string, text: string): number {
  const bytes: Uint8Array = ENCODER.encodeInto(text);
  const buf: ArrayBuffer = bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength);
  const file = fileIo.openSync(uri,
    fileIo.OpenMode.READ_WRITE | fileIo.OpenMode.CREATE | fileIo.OpenMode.TRUNC);
  try {
    const written: number = fileIo.writeSync(file.fd, buf);
    return written;
  } finally {
    fileIo.closeSync(file);
  }
}

function verifySize(uri: string, expected: number): void {
  const st = fileIo.statSync(uri);
  if (st.size !== expected) {
    throw new Error(`写入校验失败（写 ${expected} / 实际 ${st.size}）`);
  }
}

/** 生成 CSV 文本（带 UTF-8 BOM，Excel 才不会把中文当乱码）。 */
export function withBom(text: string): string {
  return '\uFEFF' + text;
}

export class Exporter {
  private ctx: common.UIAbilityContext;

  constructor(ctx: common.UIAbilityContext) {
    this.ctx = ctx;
  }

  /** 优先弹「另存为」；失败则退回应用沙箱。 */
  async saveText(fileName: string, text: string): Promise<ExportResult> {
    const content: string = withBom(text);
    const result: ExportResult = new ExportResult();

    // 1) 系统另存为
    try {
      const docPicker = new picker.DocumentViewPicker(this.ctx);
      const options = new picker.DocumentSaveOptions();
      options.newFileNames = [fileName];
      options.fileSuffixChoices = ['.csv'];
      const uris: string[] = await docPicker.save(options);
      if (uris !== undefined && uris.length > 0) {
        const written: number = writeTextSync(uris[0], content);
        const expected: number = ENCODER.encodeInto(content).length;
        if (written !== expected) {
          throw new Error(`写入校验失败（写 ${expected} / 实际 ${written}）`);
        }
        result.ok = true;
        result.path = uris[0];
        result.message = '已保存';
        return result;
      }
      // 用户取消 → 落到沙箱，至少不丢数据
      result.message = '已取消另存为，改为存到应用目录；';
    } catch (e) {
      result.message = `另存为不可用（${errText(e)}）；`;
    }

    // 2) 应用沙箱
    try {
      const path: string = `${this.ctx.filesDir}/${fileName}`;
      const written: number = writeTextSync(path, content);
      const expected: number = ENCODER.encodeInto(content).length;
      if (written !== expected) {
        throw new Error(`写入校验失败（写 ${expected} / 实际 ${written}）`);
      }
      verifySize(path, expected);
      result.ok = true;
      result.sandbox = true;
      result.path = path;
      result.message = `${result.message}已存到应用目录`;
      return result;
    } catch (e) {
      result.ok = false;
      result.message = `${result.message}写入失败：${errText(e)}`;
      return result;
    }
  }
}
