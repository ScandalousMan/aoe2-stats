// T744: both directions of `expectKnownDefect` (`./known-defect`), planted. A known defect that is
// matched loosely accepts any failure; one that is never checked for a pass outlives its fix. Each
// case below is one way a suite could be fooled, shown failing, beside the control that passes.
import { expect, test } from '@playwright/test'
import { expectKnownDefect, type KnownDefect } from './known-defect'

const LEAK: KnownDefect = {
  reason: 'Dialog traps Tab on a disabled button',
  message: /focus left the dialog during its walk/,
}

test.describe('expectKnownDefect', () => {
  test('control: the failure the defect is filed with is accepted', async () => {
    await expectKnownDefect(
      () => {
        throw new Error('x (light): focus left the dialog during its walk — <a> "Read the notice"')
      },
      LEAK,
      'x',
    )
  })

  test('control: an async failure with that message is accepted', async () => {
    await expectKnownDefect(
      async () => {
        await Promise.resolve()
        throw new Error('focus left the dialog during its walk')
      },
      LEAK,
      'x',
    )
  })

  test('a walk that throws a different error fails, naming what it threw', async () => {
    await expect(
      expectKnownDefect(
        () => {
          throw new Error('locator.waitFor: Test timeout of 30000ms exceeded.')
        },
        LEAK,
        'x (light)',
      ),
    ).rejects.toThrow(
      /x \(light\): the assertion failed, but not with the known defect's message .*focus left the dialog.*It threw: locator\.waitFor: Test timeout/,
    )
  })

  test('a walk that passes fails, telling the reader to remove the marker', async () => {
    await expect(expectKnownDefect(() => undefined, LEAK, 'x (light)')).rejects.toThrow(
      /x \(light\): the assertion passed, but this scenario is marked with a known defect .*remove its `knownDefects` marker/,
    )
  })

  test('a non-Error throw is judged by its text, not waved through', async () => {
    await expect(
      expectKnownDefect(
        () => {
          throw 'something else'
        },
        LEAK,
        'x',
      ),
    ).rejects.toThrow(/It threw: something else/)
    await expectKnownDefect(
      () => {
        throw 'focus left the dialog during its walk'
      },
      LEAK,
      'x',
    )
  })
})
